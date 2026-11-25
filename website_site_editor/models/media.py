from typing import Any

from odoo import api, models

from .access import denied, is_site_editor


class WebsiteAssets(models.AbstractModel):
    _inherit = "website.assets"

    def save_asset(self, url: str, bundle: str, content: str, file_type: str) -> Any:
        if is_site_editor(self.env):
            raise denied(self.env)
        return super().save_asset(url, bundle, content, file_type)

    def reset_asset(self, url: str, bundle: str) -> Any:
        if is_site_editor(self.env):
            raise denied(self.env)
        return super().reset_asset(url, bundle)


class ThemeUtils(models.AbstractModel):
    _inherit = "theme.utils"

    def _toggle_asset(self, key: str, active: bool) -> None:
        if is_site_editor(self.env):
            raise denied(self.env)
        return super()._toggle_asset(key, active)


class IrAttachment(models.Model):
    _inherit = "ir.attachment"

    _editor_media_fields = ("website_id", "res_model", "res_id", "public", "url", "key", "res_field")

    def _check_editor_media(self, values: "odoo.values.ir_attachment") -> None:
        site_models = {"website", "website.page", "website.menu", "ir.ui.view", "ir.asset"}
        model = values.get("res_model")
        site = self.env["website"].browse(values.get("website_id"))
        if not site and model not in site_models and not (values.get("public") and not model):
            return
        site._check_assigned_sites()
        if any(values.get(key) for key in ("url", "key", "res_field")) or model == "ir.asset":
            raise denied(self.env)
        if (record_id := values.get("res_id")) and model in site_models:
            target = self.env[model].sudo().browse(record_id)
            if (target if model == "website" else target.website_id) != site:
                raise denied(self.env)

    @api.model
    def _prepare_create_values(self, vals_list: list["odoo.values.ir_attachment"]) -> list["odoo.values.ir_attachment"]:
        values = super()._prepare_create_values(vals_list)
        if is_site_editor(self.env):
            for vals in values:
                self._check_editor_media(vals)
        return values

    def _check_existing_editor_media(self, changes: "odoo.values.ir_attachment") -> None:
        if is_site_editor(self.env):
            for values in self.sudo().read(self._editor_media_fields, load=None):
                self._check_editor_media(values)
                if changes.keys() & self._editor_media_fields:
                    self._check_editor_media(values | changes)

    def write(self, vals: "odoo.values.ir_attachment") -> bool:
        self._check_existing_editor_media(vals)
        return super().write(vals)

    @api.ondelete(at_uninstall=False)
    def _unlink_editor_media(self) -> None:
        self._check_existing_editor_media({})
