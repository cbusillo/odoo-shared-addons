from odoo.api import Environment


def apply_house_defaults_to_existing_users(env: Environment) -> None:
    internal_users = env["res.users"].with_context(active_test=False).search([("share", "=", False)])
    internal_users.write({"chatter_position": "bottom"})
    users_without_home = internal_users.filtered(lambda user: not user.action_id)
    users_without_home.write({"action_id": env.ref("house_standard.action_app_grid").id})
