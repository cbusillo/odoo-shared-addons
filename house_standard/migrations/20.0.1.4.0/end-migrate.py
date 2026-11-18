from odoo import SUPERUSER_ID, api
from odoo.addons.house_standard.hooks import apply_website_signup_default
from odoo.sql_db import Cursor


def migrate(cr: Cursor, _version: str) -> None:
    apply_website_signup_default(api.Environment(cr, SUPERUSER_ID, {}))
