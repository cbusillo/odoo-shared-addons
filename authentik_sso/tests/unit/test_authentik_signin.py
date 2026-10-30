import json
from unittest.mock import patch

from odoo import SUPERUSER_ID, api
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

    def _signin(self, validation: dict[str, object], *, access_token: str = "token-1") -> str | None:
        params = {"access_token": access_token, "state": json.dumps({})}
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
        login = self._signin(
            {"sub": "sub-new", "email": "new.staff@example.test", "name": "New Staff", "groups": ["Engineering"]}
        )

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
        login = self.Users.sudo().with_context(no_user_creation=True)._auth_oauth_signin(
            self.provider.id,
            {"sub": "sub-unknown", "email": "unknown@example.test"},
            {"access_token": "token", "state": json.dumps({})},
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
