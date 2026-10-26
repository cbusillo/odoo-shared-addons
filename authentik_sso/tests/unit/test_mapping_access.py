from odoo import Command

from ..common_imports import common
from ..fixtures.base import UnitTestCase


@common.tagged(*common.UNIT_TAGS)
class TestMappingAccess(UnitTestCase):
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
                    self.assertEqual(
                        mappings.has_access(operation), group == "base.group_system"
                    )
