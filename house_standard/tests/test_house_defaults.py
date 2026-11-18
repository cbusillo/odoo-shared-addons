from unittest.mock import patch

from odoo.addons.auth_signup.models.res_users import SignupError
from odoo.modules.migration import MigrationManager
from odoo.modules.module_graph import ModuleGraph
from odoo.tests import TransactionCase, tagged
from odoo.tools.convert import convert_file

from ..hooks import apply_house_defaults_to_existing_users


@tagged("-at_install", "post_install")
class TestHouseDefaults(TransactionCase):
    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.app_grid = cls.env.ref("house_standard.action_app_grid")

    def _create_user(self, login: str, **values: object) -> "odoo.model.res_users":
        return self.env["res.users"].create({"name": login, "login": login, **values})

    def test_new_internal_user_lands_on_app_grid_with_chatter_below(self) -> None:
        user = self._create_user("house-new-user")
        self.assertEqual(user.chatter_position, "bottom")
        self.assertEqual(user.action_id.id, self.app_grid.id)

    def test_install_moves_every_existing_user_and_keeps_chosen_home_actions(self) -> None:
        chosen_home = self.env.ref("contacts.action_contacts")
        first = self._create_user("house-existing-first", chatter_position="side", action_id=False)
        second = self._create_user("house-existing-second", chatter_position="side", action_id=False)
        archived = self._create_user("house-existing-archived", chatter_position="side", action_id=False, active=False)
        with_home = self._create_user("house-existing-home", chatter_position="side", action_id=chosen_home.id)

        apply_house_defaults_to_existing_users(self.env)

        for user in first | second | archived | with_home:
            self.assertEqual(user.chatter_position, "bottom")
        for user in first | second | archived:
            self.assertEqual(user.action_id.id, self.app_grid.id)
        self.assertEqual(with_home.action_id.id, chosen_home.id)

    def test_contacts_open_as_cards_first(self) -> None:
        first_view_mode = self.env.ref("contacts.action_contacts").views[0][1]
        self.assertEqual(first_view_mode, "kanban")

    def test_uninvited_customer_signup_is_disabled_by_default(self) -> None:
        with self.assertRaises(SignupError):
            self.env["res.users"]._signup_create_user({"name": "Uninvited", "login": "uninvited@example.test"})

    def test_odoo_com_provider_is_disabled_by_default(self) -> None:
        self.assertFalse(self.env.ref("auth_oauth.provider_openerp").enabled)

    def test_upgrades_preserve_explicit_login_choices(self) -> None:
        parameters = self.env["ir.config_parameter"].sudo()
        parameters.set_str("auth_signup.invitation_scope", "b2c")
        provider = self.env.ref("auth_oauth.provider_openerp")
        provider.enabled = True

        convert_file(self.env, "house_standard", "data/login_defaults.xml", {}, mode="update")

        user = self.env["res.users"]._signup_create_user({"name": "Chosen Signup", "login": "chosen-signup@example.test"})
        self.assertTrue(user.share)
        self.assertTrue(provider.enabled)

    def _upgrade_login_defaults(self, installed_version: str) -> None:
        graph = ModuleGraph(self.env.cr, mode="update")
        installed = self.env["ir.module.module"].search([("state", "=", "installed")])
        graph.extend(installed.mapped("name"))
        house_standard = graph["house_standard"]
        house_standard.load_state = "to upgrade"
        house_standard.load_version = installed_version
        with patch.object(self.env.registry, "_force_upgrade_scripts", set(), create=True):
            migrations = MigrationManager(self.env.cr, graph)
        migrations.migrate_module(house_standard, "post")
        migrations.migrate_module(house_standard, "end")

    def test_login_defaults_skip_a_deleted_odoo_com_provider(self) -> None:
        self.env.ref("auth_oauth.provider_openerp").unlink()

        convert_file(self.env, "house_standard", "data/login_defaults.xml", {}, mode="init", noupdate=True)
        self._upgrade_login_defaults("20.0.1.2.0")

        self.assertFalse(self.env.ref("auth_oauth.provider_openerp", raise_if_not_found=False))

    def test_first_upgrade_defaults_existing_websites_to_invitation_only(self) -> None:
        if "auth_signup_uninvited" not in self.env["website"]._fields:
            self.skipTest("Requires the website addon on the disposable test database.")
        websites = self.env["website"].search([])
        self.assertTrue(websites)
        websites.auth_signup_uninvited = "b2c"

        self._upgrade_login_defaults("20.0.1.2.0")

        self.assertEqual(set(websites.mapped("auth_signup_uninvited")), {"b2b"})

    def test_first_upgrade_keeps_odoo_com_enabled_for_linked_users(self) -> None:
        provider = self.env.ref("auth_oauth.provider_openerp")
        provider.enabled = True
        self._create_user("house-odoo-com-user", oauth_provider_id=provider.id, oauth_uid="house-test")

        self._upgrade_login_defaults("20.0.1.2.0")

        self.assertTrue(provider.enabled)
