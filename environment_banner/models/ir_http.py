import os

from odoo import api, models


class IrHttp(models.AbstractModel):
    _inherit = "ir.http"

    @api.model
    def session_info(self) -> dict:
        session_info = super().session_info()
        session_info["show_environment_banner"] = os.environ.get("PLATFORM_INSTANCE", "").strip() != "prod"
        return session_info
