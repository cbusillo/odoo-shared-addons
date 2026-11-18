import logging

from odoo.api import Environment

_logger = logging.getLogger(__name__)


def apply_house_defaults(env: Environment) -> None:
    apply_house_defaults_to_existing_users(env)
    apply_website_signup_default(env)


def apply_website_signup_default(env: Environment) -> None:
    if "website" not in env:
        return

    websites = env["website"].search([("auth_signup_uninvited", "!=", "b2b")])
    public_count = len(websites.filtered(lambda website: website.auth_signup_uninvited == "b2c"))
    websites.auth_signup_uninvited = "b2b"
    if public_count:
        _logger.warning("Changed customer sign-up from public to invitation-only on %s website(s)", public_count)


def apply_house_defaults_to_existing_users(env: Environment) -> None:
    internal_users = env["res.users"].with_context(active_test=False).search([("share", "=", False)])
    internal_users.write({"chatter_position": "bottom"})
    users_without_home = internal_users.filtered(lambda user: not user.action_id)
    users_without_home.write({"action_id": env.ref("house_standard.action_app_grid").id})
