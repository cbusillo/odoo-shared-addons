from odoo import SUPERUSER_ID, api
from odoo.addons.external_ids.migrations.preserve_seed_records import (
    preserve_seed_records,
)


def migrate(cr, version):
    preserve_seed_records(api.Environment(cr, SUPERUSER_ID, {}))
