from typing import Any

from lxml import html
from odoo import api, models

from .access import denied, is_site_editor


class IrUiView(models.Model):
    _name = "ir.ui.view"
    _inherit = ["website.site.editor.fields", "ir.ui.view"]

    def save(self, value: str, xpath: str | None = None) -> None:
        if is_site_editor(self.env):
            self.env.website._check_assigned_sites()
            if xpath is not None:
                raise denied(self.env)
            element = html.fromstring(value)
            if (element.get("data-oe-model"), element.get("data-oe-field"), element.get("data-oe-type")) != (
                "website.page",
                "site_editor_body",
                "html",
            ):
                raise denied(self.env)
            page = self.env["website.page"].sudo(False).browse(int(element.get("data-oe-id")))
            if page.website_id != self.env.website:
                raise denied(self.env)
            return super(IrUiView, self.sudo(False)).save(value, xpath)
        return super().save(value, xpath)

    def write(self, vals: "odoo.values.ir_ui_view") -> bool:
        if is_site_editor(self.env):
            raise denied(self.env)
        return super().write(vals)

    @api.model_create_multi
    def create(self, vals_list: list["odoo.values.ir_ui_view"]) -> "odoo.model.ir_ui_view":
        if is_site_editor(self.env):
            raise denied(self.env)
        return super().create(vals_list)

    @api.ondelete(at_uninstall=False)
    def _unlink_admin_template(self) -> None:
        if is_site_editor(self.env):
            raise denied(self.env)


class PageBodyHtml(models.AbstractModel):
    _inherit = "ir.qweb.field.html"

    def attributes(
        self, record: models.BaseModel, field_name: str, options: dict[str, Any], values: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        if record._name == "website.page" and field_name == "site_editor_body" and is_site_editor(self.env):
            site = record.sudo().website_id
            options = dict(options, inherit_branding=bool(site and site == self.env.website and site._allows_site_editor()))
        return super().attributes(record, field_name, options, values)
