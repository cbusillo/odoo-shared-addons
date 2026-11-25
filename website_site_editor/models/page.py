from typing import Any

from odoo import api, fields, models
from odoo.tools import html_translate

from .access import denied, is_site_editor


class WebsitePage(models.Model):
    _name = "website.page"
    _inherit = ["website.site.editor.fields", "website.page"]

    _site_editor_fields = frozenset({"url", "website_indexed", "site_editor_body"})

    site_editor_body = fields.Html(
        string="Editable page body", translate=html_translate, sanitize_attributes=False, sanitize_style=True
    )

    def write(self, vals: "odoo.values.website_page") -> bool:
        if is_site_editor(self.env):
            if vals.keys() - self._site_editor_fields or any(not page.website_id for page in self):
                raise denied(self.env)
            self.website_id._check_assigned_sites()
        result = super().write(vals)
        if "site_editor_body" in vals:
            self.env.transaction.invalidate_ormcache("templates")
        return result

    @api.model
    def action_site_editor_pages(self) -> dict[str, Any]:
        sites = self.env["website"].sudo().search([("site_editor_ids", "in", [self.env.uid])])
        return {
            "type": "ir.actions.act_window",
            "name": self.env._("Assigned pages"),
            "res_model": "website.page",
            "views": [(self.env.ref("website_site_editor.page_list").id, "list")],
            "domain": [("website_id", "in", sites.ids)],
        }
