import logging

from odoo import SUPERUSER_ID, api
from odoo.sql_db import Cursor
from odoo.tools.parse_version import parse_version

_logger = logging.getLogger(__name__)


def migrate(cr: Cursor, version: str) -> None:
    env = api.Environment(cr, SUPERUSER_ID, {})
    first_database_defaults = parse_version(version) < parse_version("20.0.1.3.0")
    if first_database_defaults:
        parameters = env["ir.config_parameter"]
        was_public = parameters.get_str("auth_signup.invitation_scope") == "b2c"
        parameters.set_str("auth_signup.invitation_scope", "b2b")
        if was_public:
            _logger.warning("Changed database-wide customer sign-up from public to invitation-only")

    provider = env.ref("auth_oauth.provider_openerp", raise_if_not_found=False)
    if not provider:
        return

    linked_count = env["res.users"].with_context(active_test=False).search_count([("oauth_provider_id", "=", provider.id)])
    if linked_count:
        _logger.warning("Kept Odoo.com Accounts unchanged (enabled=%s) with %s linked user(s)", provider.enabled, linked_count)
    elif first_database_defaults:
        provider.enabled = False
