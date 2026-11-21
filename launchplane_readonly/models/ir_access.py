from collections.abc import Iterator

from odoo import models

from .base import STAFF_OBSERVER_READ_CURSOR


class IrAccess(models.Model):
    _inherit = "ir.access"

    def _get_access_context(self) -> Iterator:
        yield from super()._get_access_context()
        yield self.env.cr is STAFF_OBSERVER_READ_CURSOR.get()
