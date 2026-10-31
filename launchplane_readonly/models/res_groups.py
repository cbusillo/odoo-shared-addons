from odoo import models

from ..policy import GROUP


class ResGroups(models.Model):
    _inherit = "res.groups"

    def _get_light_group_xmlids(self) -> tuple[str, ...]:
        return (*super()._get_light_group_xmlids(), GROUP)
