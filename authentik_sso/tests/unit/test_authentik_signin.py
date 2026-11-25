import json
from unittest import TestCase
from unittest.mock import patch

from odoo import SUPERUSER_ID, Command, api
from odoo.exceptions import AccessDenied

from ..common_imports import common
from ..fixtures.base import UnitTestCase


@common.tagged(*common.UNIT_TAGS)
class TestAuthentikSignin(UnitTestCase):
    def setUp(self) -> None:
        super().setUp()
        provider_model = self.env["auth.oauth.provider"]
        self.provider = provider_model.search([("name", "=", "Authentik")], limit=1) or provider_model.create(
            {
                "name": "Authentik",
                "auth_endpoint": "https://auth.example.test/authorize",
                "validation_endpoint": "https://auth.example.test/userinfo",
                "body": "Login with Authentik",
                "enabled": True,
            }
        )
        self.engineering_group = self.env["res.groups"].create({"name": "Signin Engineering"})
        self.AuthentikMapping.create(
            {
                "authentik_group": "Engineering",
                "odoo_groups": [(6, 0, [self.engineering_group.id])],
                "sequence": 5,
            }
        )
        # Uninvited signup stays closed; Authentik users must still be created.
        self.env["ir.config_parameter"].sudo().set_str("auth_signup.invitation_scope", "b2b")

    def _signin(self, validation: dict[str, object], *, access_token: str = "token-1", token: str | None = None) -> str | None:
        params = {"access_token": access_token, "state": json.dumps({"t": token})}
        self.env.flush_all()
        anonymous_env = api.Environment(self.env.cr, None, {})
        with patch.object(self.env.cr.transaction, "default_env", anonymous_env):
            login = anonymous_env["res.users"].with_user(SUPERUSER_ID)._auth_oauth_signin(self.provider.id, validation, params)
            anonymous_env.cr.flush()
            return login

    def test_existing_user_signs_in_and_gets_mapped_groups(self) -> None:
        user = self.Users.create(
            {
                "name": "Existing Staff",
                "login": "existing.staff@example.test",
                "oauth_provider_id": self.provider.id,
                "oauth_uid": "sub-existing",
            }
        )

        login = self._signin(
            {"sub": "sub-existing", "email": "existing.staff@example.test", "groups": ["Engineering"]},
            access_token="token-existing",
        )

        self.assertEqual(login, user.login)
        self.assertEqual(user.sudo().oauth_access_token, "token-existing")
        self.assertIn(user, self.engineering_group.user_ids)

    def test_anonymous_transaction_creates_internal_oauth_user(self) -> None:
        login = self._signin({"sub": "sub-new", "email": "new.staff@example.test", "name": "New Staff", "groups": ["Engineering"]})

        user = self.Users.search([("login", "=", login)])
        self.assertEqual(login, "new.staff@example.test")
        self.assertEqual(user.oauth_uid, "sub-new")
        self.assertEqual(user.oauth_provider_id, self.provider)
        self.assertEqual(user.name, "New Staff")
        self.assertTrue(user.active)
        self.assertFalse(user.share)
        self.assertTrue(user.has_group("base.group_user"))
        self.assertIn(user, self.engineering_group.user_ids)

    def test_missing_subject_is_denied(self) -> None:
        with self.assertRaises(AccessDenied):
            self._signin({"groups": ["Engineering"]})

    def test_unknown_user_without_creation_returns_nothing(self) -> None:
        login = (
            self.Users.sudo()
            .with_context(no_user_creation=True)
            ._auth_oauth_signin(
                self.provider.id,
                {"sub": "sub-unknown", "email": "unknown@example.test"},
                {"access_token": "token", "state": json.dumps({})},
            )
        )

        self.assertIsNone(login)
        self.assertFalse(self.Users.search([("login", "=", "unknown@example.test")]))

    def test_existing_local_user_is_not_linked_by_email(self) -> None:
        local_user = self.Users.create({"name": "Local Staff", "login": "local.staff@example.test"})

        # Not assertRaises: Odoo's version rolls back a savepoint, which would
        # hide an aborted transaction or a link written before the refusal.
        try:
            self._signin({"sub": "sub-local", "email": "local.staff@example.test"})
        except AccessDenied:
            pass
        else:
            self.fail("Sign-in with a taken login was not refused.")

        self.env.invalidate_all()
        self.assertFalse(local_user.oauth_uid)
        self.assertEqual(self.Users.search_count([("login", "=", "local.staff@example.test")]), 1)

    def _other_provider_signin(self, subject: str) -> str | None:
        provider = self.env.ref("auth_oauth.provider_openerp")
        users = self.Users.with_user(SUPERUSER_ID).with_context(oauth_use_internal_template=True)
        return users._auth_oauth_signin(
            provider.id,
            {"user_id": subject, "email": f"{subject}@example.invalid", "name": subject},
            {"access_token": "other-provider-token", "state": json.dumps({})},
        )

    def test_other_provider_uses_native_portal_template(self) -> None:
        self.env["ir.config_parameter"].sudo().set_str("auth_signup.invitation_scope", "b2c")

        self._select_existing_users()
        login = self._other_provider_signin("other-portal")

        user = self.Users.search([("login", "=", login)])
        self.assertTrue(user.active)
        self.assertTrue(user.share)
        self.assertTrue(user.has_group("base.group_portal"))
        self.assertFalse(user.has_group("base.group_user"))
        self.assertEqual(user.oauth_provider_id, self.env.ref("auth_oauth.provider_openerp"))

    def test_other_provider_keeps_native_invitation_requirement(self) -> None:
        with self.assertRaises(AccessDenied):
            self._other_provider_signin("other-uninvited")

        self.assertFalse(self.Users.search([("login", "=", "other-uninvited@example.invalid")]))

    def test_existing_other_provider_keeps_its_groups(self) -> None:
        provider = self.env.ref("auth_oauth.provider_openerp")
        user = self.Users.create(
            {
                "name": "Other Provider Staff",
                "login": "existing-other@example.invalid",
                "oauth_provider_id": provider.id,
                "oauth_uid": "existing-other",
            }
        )
        groups = user.group_ids

        login = self._other_provider_signin("existing-other")

        self.assertEqual(login, user.login)
        self.assertEqual(user.group_ids, groups)
        self.assertEqual(user.sudo().oauth_access_token, "other-provider-token")

    def _select_existing_users(self) -> None:
        self.env["ir.config_parameter"].sudo().set_str("authentik_sso.callback_mode", "existing_user")

    def _user_auth_state(self) -> list[dict]:
        return (
            self.Users.sudo()
            .with_context(active_test=False)
            .search([])
            .read(["oauth_provider_id", "oauth_uid", "oauth_access_token", "group_ids", "all_group_ids"])
        )

    def _assert_existing_user_refused(self, claims: dict[str, object], token: str | None = None) -> None:
        before = self._user_auth_state()
        with TestCase.assertRaises(self, AccessDenied):
            self._signin(claims, token=token)
        self.env.invalidate_all()
        self.assertEqual(self._user_auth_state(), before)

    def test_existing_mode_links_by_login_or_email_and_refreshes_only_token(self) -> None:
        self._select_existing_users()
        for field in ("login", "email"):
            address = f"staff.{field}@example.test"
            user = self.Users.create({"name": field, "login": field, field: address})
            count = self.Users.with_context(active_test=False).search_count([])
            direct, effective = user.group_ids, user.all_group_ids
            claims = {"sub": field, "email": address.upper(), "email_verified": True, "groups": ["Engineering"]}
            self.assertEqual(self._signin(claims), user.login)
            self.assertEqual(
                (user.oauth_provider_id, user.oauth_uid, user.sudo().oauth_access_token), (self.provider, field, "token-1")
            )
            self.assertEqual((user.group_ids, user.all_group_ids), (direct, effective))
            self.assertEqual(self._signin({"sub": field}, access_token="repeat"), user.login)
            self.assertEqual(user.sudo().oauth_access_token, "repeat")
            self.assertEqual((user.group_ids, user.all_group_ids), (direct, effective))
            self.assertEqual(self.Users.with_context(active_test=False).search_count([]), count)

    def test_existing_mode_requires_one_available_user_and_raw_verified_email(self) -> None:
        self._select_existing_users()
        address = "staff@example.test"
        user = self.Users.create({"name": "Candidate", "login": address})
        claims = {"sub": "fixture-subject", "email": address, "email_verified": True}
        for altered in (
            {"sub": None},
            {"email": None, "preferred_username": address},
            {"email": [address]},
            {"email_verified": "true"},
            {"email_verified": False},
            {"email": "unknown@example.test"},
        ):
            with self.subTest(altered=altered):
                self._assert_existing_user_refused({**claims, **altered})
        user.write({"oauth_provider_id": self.env.ref("auth_oauth.provider_openerp").id, "oauth_uid": claims["sub"]})
        self._assert_existing_user_refused(claims)
        user.write({"oauth_provider_id": False, "oauth_uid": False})
        other = self.Users.create({"name": "Duplicate", "login": "duplicate", "email": address})
        self._assert_existing_user_refused(claims)
        other.active = False
        self.provider.enabled = False
        self._assert_existing_user_refused(claims)
        self.provider.enabled = True
        self.assertEqual(self._signin(claims), user.login)

    def test_existing_mode_denies_ineligible_subject_before_considering_email(self) -> None:
        self._select_existing_users()
        address = "available@example.test"
        self.Users.create({"name": "Eligible", "login": address})
        other = self.Users.create({"name": "Other", "login": "other@example.test"})
        for role in ("archived", "portal"):
            if role == "archived":
                other.active = False
            else:
                other.write({"active": True, "group_ids": [Command.set(self.env.ref("base.group_portal").ids)]})
            self._assert_existing_user_refused({"sub": role, "email": other.login, "email_verified": True})
            other.write({"oauth_provider_id": self.provider.id, "oauth_uid": role})
            self._assert_existing_user_refused({"sub": role, "email": address, "email_verified": True})
            other.write({"oauth_provider_id": False, "oauth_uid": False})

    def test_existing_mode_leaves_invitation_and_reset_for_native_flows(self) -> None:
        self._select_existing_users()
        user = self.Users.create({"name": "Invited staff", "login": "invited@example.test"})
        claims = {"sub": "invited", "email": user.login, "email_verified": True}
        for kind in ("signup", "reset"):
            user.partner_id.signup_prepare(kind)
            token = user.partner_id._generate_signup_token()
            self._assert_existing_user_refused(claims, token)
            user.write({"oauth_provider_id": self.provider.id, "oauth_uid": claims["sub"]})
            self._assert_existing_user_refused(claims, token)
            self.assertEqual(user.partner_id.signup_type, kind)
            login, _ = self.Users.signup({"password": "fixture-only-password"}, token)
            self.assertEqual(login, user.login)
            self.assertFalse(user.partner_id.signup_type)
            user.write({"oauth_provider_id": False, "oauth_uid": False})

    def test_invalid_stored_callback_mode_refuses_before_writes(self) -> None:
        self.env["ir.config_parameter"].sudo().set_str("authentik_sso.callback_mode", "unknown")
        self._assert_existing_user_refused({"sub": "new", "email": "new@example.test", "email_verified": True})

    def test_validated_callback_links_only_after_provider_accepts(self) -> None:
        self._select_existing_users()
        user = self.Users.create({"name": "Valid subject", "login": "validated@example.test"})
        params = {"access_token": "fixture-token", "state": "{}"}
        before = self._user_auth_state()
        with patch.object(type(self.Users), "_auth_oauth_rpc", return_value={}), TestCase.assertRaises(self, AccessDenied):
            self.Users.with_user(SUPERUSER_ID).auth_oauth(self.provider.id, params)
        self.env.invalidate_all()
        self.assertEqual(self._user_auth_state(), before)
        claims = {"sub": "validated", "email": user.login, "email_verified": True}
        with patch.object(type(self.Users), "_auth_oauth_rpc", return_value=claims):
            _, login, token = self.Users.with_user(SUPERUSER_ID).auth_oauth(self.provider.id, params)
        self.assertEqual((login, token, user.oauth_uid), (user.login, params["access_token"], "validated"))

    def test_invited_signup_remains_available_to_provisioning_and_other_providers(self) -> None:
        for provider in (self.provider, self.env.ref("auth_oauth.provider_openerp")):
            if provider != self.provider:
                self._select_existing_users()
            address = f"invited-{provider.id}@example.test"
            partner = self.env["res.partner"].create({"name": "Invited", "email": address})
            partner.signup_prepare()
            params = {"access_token": "fixture-token", "state": json.dumps({"t": partner._generate_signup_token()})}
            login = self.Users.with_user(SUPERUSER_ID)._auth_oauth_signin(
                provider.id, {"user_id": "invited", "email": address}, params
            )
            self.assertEqual(login, address)
            self.assertEqual(partner.user_ids.oauth_provider_id, provider)
            self.assertFalse(partner.signup_type)
