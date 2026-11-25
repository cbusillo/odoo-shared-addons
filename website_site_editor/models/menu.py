from urllib.parse import urlsplit

from odoo import api, models

from .access import denied, is_site_editor


class WebsiteMenu(models.Model):
    _name = "website.menu"
    _inherit = ["website.site.editor.fields", "website.menu"]

    _site_editor_fields = frozenset({"name", "url", "manual_url", "page_id", "new_window", "sequence", "parent_id", "website_id"})

    def _check_site_menu_values(self, vals: "odoo.values.website_menu", site: "odoo.model.website") -> None:
        site._check_assigned_sites()
        for key, model in (("parent_id", "website.menu"), ("page_id", "website.page")):
            if vals.get(key):
                related_site = self.env[model].sudo().browse(vals[key]).website_id
                if related_site != site and (key == "parent_id" or related_site):
                    raise denied(self.env)
        for key in ("url", "manual_url"):
            if vals.get(key) and urlsplit(vals[key]).scheme.lower() not in {"", "https", "http", "mailto", "tel"}:
                raise denied(self.env)

    @api.model_create_multi
    def create(self, vals_list: list["odoo.values.website_menu"]) -> "odoo.model.website_menu":
        if not is_site_editor(self.env):
            return super().create(vals_list)
        clean_context = {key: value for key, value in self.env.context.items() if not key.startswith("default_")}
        for vals in vals_list:
            if vals.keys() - self._site_editor_fields - {"website_id"}:
                raise denied(self.env)
            site = self.env["website"].browse(vals.get("website_id", self.env.website.id))
            self._check_site_menu_values(vals, site)
            vals["website_id"] = site.id
            vals.setdefault("parent_id", site.menu_id.id)
        return super(WebsiteMenu, self.with_context(clean_context)).create(vals_list)

    def write(self, vals: "odoo.values.website_menu") -> bool:
        if is_site_editor(self.env):
            vals = dict(vals)
            if "id" in vals and vals.pop("id") != self.id:
                raise denied(self.env)
            if "is_mega_menu" in vals and any(menu.is_mega_menu != vals["is_mega_menu"] for menu in self):
                raise denied(self.env)
            vals.pop("is_mega_menu", None)
            if "website_id" in vals or vals.keys() - self._site_editor_fields:
                raise denied(self.env)
            for menu in self:
                self._check_site_menu_values(vals, menu.website_id)
        return super().write(vals)

    @api.ondelete(at_uninstall=False)
    def _unlink_assigned_menu(self) -> None:
        if is_site_editor(self.env):
            descendants = self.sudo().search([("id", "child_of", self.ids)])
            if any(not menu.website_id or not menu.parent_id for menu in descendants):
                raise denied(self.env)
            descendants.website_id._check_assigned_sites()
