from collections.abc import Callable
from typing import Any, Literal

from odoo import api, fields, models
from odoo.tools import html_translate

from .access import PAGE_FIELD_ACCESS, denied, is_site_editor


class WebsitePage(models.Model):
    _name = "website.page"
    _inherit = ["website.site.editor.fields", "website.page"]

    _site_editor_fields = frozenset({"url", "website_indexed", "site_editor_body"})

    site_editor_body_enabled = fields.Boolean(string="Enable assigned body editing")
    site_editor_body = fields.Html(string="Editable page body", translate=html_translate, sanitize_attributes=False)

    def _access_domain(self, operation: str) -> fields.Domain:
        if operation == "write" and is_site_editor(self.env):
            scoped = self.with_context(site_editor_page_field_access=PAGE_FIELD_ACCESS)
            return super(WebsitePage, scoped)._access_domain(operation)
        return super()._access_domain(operation)

    def _check_site_editor_page_fields(self, names: set[str]) -> None:
        if names - self._site_editor_fields or any(not page.website_id for page in self):
            raise denied(self.env)
        self.website_id._check_assigned_sites()
        if "site_editor_body" in names and any(not page.site_editor_body_enabled for page in self):
            raise denied(self.env)

    def _has_field_access(self, field: fields.Field, operation: Literal["read", "write"]) -> bool:
        if field.name == "site_editor_body_enabled" and operation == "write" and not self.env.is_system():
            return False
        return super()._has_field_access(field, operation)

    def _update_field_translations(
        self, field_name: str, translations: dict[str, Any], digest: Callable | None = None, source_lang: str = ""
    ) -> bool:
        if is_site_editor(self.env):
            self._check_site_editor_page_fields({field_name})
        return super()._update_field_translations(field_name, translations, digest, source_lang)

    def write(self, vals: "odoo.values.website_page") -> Literal[True]:
        pages = self
        if is_site_editor(self.env):
            self._check_site_editor_page_fields(set(vals))
            pages = self.with_prefetch(self.ids)
        result = super(WebsitePage, pages).write(vals)
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
