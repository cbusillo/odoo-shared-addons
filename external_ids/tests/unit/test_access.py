from odoo import Command
from odoo.exceptions import AccessError

from ..common_imports import common
from ..fixtures.base import UnitTestCase


@common.tagged(*common.UNIT_TAGS)
class TestExternalIdentityAccess(UnitTestCase):
    def test_external_users_cannot_manage_rename_wizards(self) -> None:
        portal = self.env["res.users"].create(
            {
                "name": "Wizard portal",
                "login": "wizard_portal",
                "group_ids": [Command.set([self.env.ref("base.group_portal").id])],
            }
        )
        for user in (portal, self.env.ref("base.public_user")):
            wizard = self.env["external.system.url.rename.wizard"].with_user(user)
            self.assertFalse(wizard.env.su)
            for operation in ("create", "read", "write", "unlink"):
                with self.subTest(user=user.login, operation=operation):
                    self.assertFalse(wizard.has_access(operation))

    def test_internal_read_admin_crud_and_portal_denial(self) -> None:
        for group in ("base.group_system", "base.group_user", "base.group_portal"):
            user = self.env["res.users"].create(
                {
                    "name": group,
                    "login": group,
                    "group_ids": [Command.set([self.env.ref(group).id])],
                }
            )
            for model_name in ("external.system", "external.system.url", "external.id"):
                model = self.env[model_name].with_user(user)
                self.assertFalse(model.env.su)
                for operation in ("create", "read", "write", "unlink"):
                    with self.subTest(group=group, model=model_name, operation=operation):
                        allowed = group == "base.group_system" or (group == "base.group_user" and operation == "read")
                        self.assertEqual(model.has_access(operation), allowed)

    def test_rename_wizard_keeps_creator_and_target_permissions(self) -> None:
        system = self.ExternalSystem.create({"name": "Access fixture", "code": "access_fixture"})
        template = self.env["external.system.url"].create(
            {
                "name": "Fixture URL",
                "code": "fixture",
                "system_id": system.id,
                "template": "https://example.test/{id}",
            }
        )
        users = self.env["res.users"].create(
            [
                {
                    "name": login,
                    "login": login,
                    "group_ids": [Command.set([self.env.ref("base.group_user").id])],
                }
                for login in ("wizard_creator", "wizard_other")
            ]
        )
        wizard = (
            self.env["external.system.url.rename.wizard"]
            .with_user(users[0])
            .create(
                {
                    "url_id": template.id,
                    "new_code": "renamed",
                }
            )
        )
        self.assertEqual(wizard.new_code, "renamed")
        with self.assertRaises(AccessError):
            wizard.with_user(users[1]).read(["new_code"])
        with self.assertRaises(AccessError):
            wizard.action_rename()
        self.assertEqual(template.code, "fixture")

    def test_internal_user_reads_external_links_without_model_access(self) -> None:
        system = self.ExternalSystem.create(
            {
                "name": "Link fixture",
                "code": "link_fixture",
                "url": "https://links.example.test",
            }
        )
        self.env["external.system.url"].create(
            {
                "name": "Admin link",
                "code": "admin",
                "system_id": system.id,
                "res_model_id": self.env["ir.model"]._get_id("res.partner"),
                "template": "{base}/items/{id}",
            }
        )
        partner = self.Partner.create({"name": "Linked partner"})
        external_id = self.ExternalId.create(
            {
                "res_model": "res.partner",
                "res_id": partner.id,
                "system_id": system.id,
                "external_id": "4242",
            }
        )
        user = self.env["res.users"].create(
            {
                "name": "Link reader",
                "login": "link_reader",
                "group_ids": [Command.set([self.env.ref("base.group_user").id])],
            }
        )
        self.assertFalse(self.env["ir.model"].with_user(user).has_access("read"))

        self.assertEqual(external_id.with_user(user).get_url("admin"), external_id.get_url("admin"))
        self.assertTrue(external_id.get_url("admin"))

    def test_internal_user_reads_inferred_resource_links_without_model_access(
        self,
    ) -> None:
        system = self.ExternalSystem.create(
            {
                "name": "Inferred link fixture",
                "code": "inferred_links",
                "url": "https://links.example.test",
            }
        )
        self.env["external.system.url"].create(
            {
                "name": "Admin link",
                "code": "admin",
                "system_id": system.id,
                "resource": "item",
                "template": "{base}/items/{id}",
            }
        )
        user = self.env["res.users"].create(
            {
                "name": "Inferred link reader",
                "login": "inferred_link_reader",
                "group_ids": [Command.set([self.env.ref("base.group_user").id])],
            }
        )
        self.env["ir.access"].create(
            {
                "name": "External identity fixture reader",
                "model_id": self.env["ir.model"]._get("external.id.fixture").id,
                "group_id": self.env.ref("base.group_user").id,
                "operation": "r",
            }
        )
        record = self.FixtureRecord.create({"name": "Inferred link record"})
        record.external.inferred_links.item.id = "4242"
        self.assertFalse(self.env["ir.model"].with_user(user).has_access("read"))

        self.assertEqual(
            record.with_user(user).get_external_url("inferred_links", "admin"),
            record.get_external_url("inferred_links", "admin"),
        )
        self.assertTrue(record.get_external_url("inferred_links", "admin"))
