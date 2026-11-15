from odoo.tests import TransactionCase, tagged


@tagged("-at_install", "post_install")
class TestHouseDefaults(TransactionCase):
    def test_new_internal_user_lands_on_app_grid_with_chatter_below(self) -> None:
        user = self.env["res.users"].create({"name": "House Default User", "login": "house-default-user"})
        self.assertEqual(user.chatter_position, "bottom")
        self.assertEqual(user.action_id.id, self.env.ref("house_standard.action_app_grid").id)

    def test_existing_internal_users_were_converted_at_install(self) -> None:
        admin = self.env.ref("base.user_admin")
        self.assertEqual(admin.chatter_position, "bottom")
        self.assertEqual(admin.action_id.id, self.env.ref("house_standard.action_app_grid").id)

    def test_user_can_still_move_chatter_beside_the_form(self) -> None:
        user = self.env["res.users"].create({"name": "House Side User", "login": "house-side-user"})
        user.with_user(user).write({"chatter_position": "side"})
        self.assertEqual(user.chatter_position, "side")

    def test_contacts_open_as_cards_first(self) -> None:
        first_view_mode = self.env.ref("contacts.action_contacts").views[0][1]
        self.assertEqual(first_view_mode, "kanban")
