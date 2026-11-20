from odoo import Command
from odoo.exceptions import AccessError
from odoo.orm.models import get_public_method

from ..common_imports import common
from ..fixtures.base import UnitTestCase


@common.tagged(*common.UNIT_TAGS)
class TestMappingAccess(UnitTestCase):
    def test_configuration_methods_are_server_only(self) -> None:
        for model, method in (
            (self.env["authentik.sso.config"], "apply_from_values"),
            (self.AuthentikMapping, "ensure_default_mappings"),
        ):
            with self.subTest(model=model._name, method=method), self.assertRaises(AccessError):
                get_public_method(model, method)

    def test_only_system_users_manage_group_mappings(self) -> None:
        for group in ("base.group_system", "base.group_user", "base.group_portal"):
            user = self.env["res.users"].create(
                {
                    "name": group,
                    "login": group,
                    "group_ids": [Command.set([self.env.ref(group).id])],
                }
            )
            mappings = self.AuthentikMapping.with_user(user)
            self.assertFalse(mappings.env.su)
            for operation in ("create", "read", "write", "unlink"):
                with self.subTest(group=group, operation=operation):
                    self.assertEqual(mappings.has_access(operation), group == "base.group_system")
