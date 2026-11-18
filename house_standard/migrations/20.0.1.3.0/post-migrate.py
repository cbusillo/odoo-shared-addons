from odoo import SUPERUSER_ID, api
from odoo.sql_db import Cursor
from odoo.tools.convert import convert_file


def migrate(cr: Cursor, _version: str) -> None:
    env = api.Environment(cr, SUPERUSER_ID, {})
    convert_file(env, "house_standard", "data/login_defaults.xml", {}, mode="init", noupdate=True)
