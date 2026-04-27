from ..common_imports import common
from ..fixtures.base import UnitTestCase


@common.tagged(*common.UNIT_TAGS)
class TestAuthentikSso(UnitTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.ConfigParameter = self.env["ir.config_parameter"].sudo()

    def test_normalize_authentik_validation_defaults(self) -> None:
        payload = {"sub": "user-1", "email": "user@example.com"}

        normalized = self.Users._normalize_authentik_validation(payload)

        self.assertEqual(normalized.get("user_id"), "user-1")
        self.assertEqual(normalized.get("login"), "user@example.com")
        self.assertEqual(normalized.get("email"), "user@example.com")
        self.assertEqual(normalized.get("name"), "user@example.com")

    def test_normalize_authentik_validation_empty_claim_overrides(self) -> None:
        payload = {"sub": "user-2", "email": "user2@example.com"}

        self.ConfigParameter.set_param("authentik_sso.user_id_claims", " ")
        self.ConfigParameter.set_param("authentik_sso.login_claims", " ")
        normalized = self.Users._normalize_authentik_validation(payload)

        self.assertEqual(normalized.get("user_id"), "user-2")
        self.assertEqual(normalized.get("login"), "user2@example.com")
        self.assertEqual(normalized.get("email"), "user2@example.com")

    def test_extract_authentik_groups(self) -> None:
        payload = {"roles": ["Admins", " Users ", ""]}

        self.ConfigParameter.set_param("authentik_sso.group_claim", "roles")
        groups = self.Users._extract_authentik_groups(payload)

        self.assertEqual(groups, {"Admins", "Users"})

    def test_apply_from_values_stores_runtime_settings(self) -> None:
        self.env["authentik.sso.config"].apply_from_values(
            {
                "admin_group": "Odoo Admins",
                "group_claim": "roles",
                "login_claims": "preferred_username,email",
                "name_claims": "display_name,email",
                "provider_name": "Internal SSO",
                "user_id_claims": "sub,email",
            }
        )

        self.assertEqual(
            self.ConfigParameter.get_param("authentik_sso.admin_group"), "Odoo Admins"
        )
        self.assertEqual(
            self.ConfigParameter.get_param("authentik_sso.group_claim"), "roles"
        )
        self.assertEqual(
            self.ConfigParameter.get_param("authentik_sso.login_claims"),
            "preferred_username,email",
        )
        self.assertEqual(
            self.ConfigParameter.get_param("authentik_sso.name_claims"),
            "display_name,email",
        )
        self.assertEqual(
            self.ConfigParameter.get_param("authentik_sso.provider_name"),
            "Internal SSO",
        )
        self.assertEqual(
            self.ConfigParameter.get_param("authentik_sso.user_id_claims"), "sub,email"
        )

    def test_apply_from_values_creates_provider(self) -> None:
        self.env["authentik.sso.config"].apply_from_values(
            {
                "base_url": "https://auth.example.com/",
                "client_id": "client-123",
                "login_label": "Login with Authentik",
            }
        )

        provider = self.env["auth.oauth.provider"].search(
            [("name", "=", "Authentik")], limit=1
        )
        self.assertTrue(provider)
        self.assertEqual(provider.client_id, "client-123")
        self.assertEqual(
            provider.auth_endpoint, "https://auth.example.com/application/o/authorize/"
        )
        self.assertEqual(
            provider.validation_endpoint,
            "https://auth.example.com/application/o/userinfo/",
        )
        self.assertTrue(provider.enabled)

    def test_sync_authentik_groups_applies_mapping(self) -> None:
        provider = self.env["auth.oauth.provider"].create(
            {
                "name": "Authentik",
                "auth_endpoint": "https://auth.example.com/authorize",
                "validation_endpoint": "https://auth.example.com/userinfo",
                "body": "Login with Authentik",
                "enabled": True,
            }
        )
        engineering_group = self.env["res.groups"].create({"name": "Engineering"})
        mapping = self.AuthentikMapping.create(
            {
                "authentik_group": "Engineering",
                "odoo_groups": [(6, 0, [engineering_group.id])],
                "sequence": 5,
            }
        )
        self.assertTrue(mapping)

        self.env["ir.model.data"].create(
            {
                "name": "engineering_group",
                "module": "authentik_sso",
                "model": "res.groups",
                "res_id": engineering_group.id,
                "noupdate": True,
            }
        )
        user = self.env["res.users"].create(
            {
                "name": "OAuth User",
                "login": "oauth_user",
            }
        )

        self.Users._sync_authentik_groups(
            user, {"groups": ["Engineering"]}, provider.id
        )

        self.assertIn(user, engineering_group.user_ids)
        self.assertTrue(user.has_group("base.group_user"))

    def test_sync_authentik_groups_uses_fallback_mapping(self) -> None:
        provider = self.env["auth.oauth.provider"].create(
            {
                "name": "Authentik",
                "auth_endpoint": "https://auth.example.com/authorize",
                "validation_endpoint": "https://auth.example.com/userinfo",
                "body": "Login with Authentik",
                "enabled": True,
            }
        )
        fallback_group = self.env["res.groups"].create({"name": "Fallback Team"})
        fallback_mapping = self.AuthentikMapping.search(
            [("is_fallback", "=", True)], limit=1
        )
        if not fallback_mapping:
            fallback_mapping = self.AuthentikMapping.create({"is_fallback": True})
        fallback_mapping.write({"odoo_groups": [(4, fallback_group.id)]})
        user = self.env["res.users"].create(
            {
                "name": "Fallback User",
                "login": "fallback_user",
            }
        )

        self.Users._sync_authentik_groups(user, {}, provider.id)

        self.assertIn(user, fallback_group.user_ids)

    def test_sync_authentik_groups_without_mapping_logs_warning(self) -> None:
        provider = self.env["auth.oauth.provider"].create(
            {
                "name": "Authentik",
                "auth_endpoint": "https://auth.example.com/authorize",
                "validation_endpoint": "https://auth.example.com/userinfo",
                "body": "Login with Authentik",
                "enabled": True,
            }
        )
        self.AuthentikMapping.search([]).unlink()
        user = self.env["res.users"].create(
            {
                "name": "No Mapping User",
                "login": "no_mapping_user",
            }
        )

        with self.assertLogs(
            "odoo.addons.authentik_sso.models.res_users", level="WARNING"
        ) as log_capture:
            self.Users._sync_authentik_groups(
                user, {"groups": ["Engineering"]}, provider.id
            )

        warning_messages = " ".join(log_capture.output)
        self.assertIn("no mappings configured", warning_messages)

    def test_ensure_default_mappings_does_not_override_custom_admin_mapping(
        self,
    ) -> None:
        admin_user = self.env.ref("base.user_admin")
        system_group = self.env.ref("base.group_system")
        mapping = self.env.ref("authentik_sso.authentik_group_mapping_admins")

        extra_group = self.env["res.groups"].create({"name": "Extra Admin"})
        admin_user.write({"group_ids": [(4, extra_group.id)]})

        mapping.write({"odoo_groups": [(6, 0, [system_group.id])]})
        self.AuthentikMapping.ensure_default_mappings()
        mapping = self.AuthentikMapping.browse(mapping.id)
        self.assertIn(extra_group.id, mapping.odoo_groups.ids)

        mapping.write({"odoo_groups": [(3, extra_group.id)]})
        group_ids_before = set(mapping.odoo_groups.ids)
        self.assertNotIn(extra_group.id, group_ids_before)

        self.AuthentikMapping.ensure_default_mappings()
        mapping = self.AuthentikMapping.browse(mapping.id)
        group_ids_after = set(mapping.odoo_groups.ids)
        self.assertEqual(group_ids_after, group_ids_before)
