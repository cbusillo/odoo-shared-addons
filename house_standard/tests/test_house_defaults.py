from odoo.addons.auth_signup.models.res_users import SignupError
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
