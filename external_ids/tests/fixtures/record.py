from odoo import fields, models

from odoo.addons.external_ids.models.external_reference import ExternalIdBinding


class ExternalIdFixture(models.Model):
    _register = False
    _module = "external_ids"
    _name = "external.id.fixture"
    _description = "External ID Fixture"
    _inherit = ["external.id.mixin"]
    _external_id_binding = ExternalIdBinding(system_code="sample")

    create_uid = fields.Many2one("res.users", readonly=True)
    create_date = fields.Datetime(readonly=True)
    write_uid = fields.Many2one("res.users", readonly=True)
    write_date = fields.Datetime(readonly=True)
    name = fields.Char(required=True)
    active = fields.Boolean(default=True)
