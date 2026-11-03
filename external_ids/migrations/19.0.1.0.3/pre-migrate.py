from odoo import SUPERUSER_ID, api
from odoo.addons.external_ids.migrations.preserve_seed_records import (
    preserve_seed_records,
)
from odoo.sql_db import Cursor


def migrate(cr: Cursor, version: str | None) -> None:
    preserve_seed_records(api.Environment(cr, SUPERUSER_ID, {}))
