from typing import Any

from odoo import api, fields, models

from .access import denied, is_site_editor


class Website(models.Model):
    _name = "website"
    _inherit = ["website.site.editor.fields", "website"]

    _site_editor_fields = frozenset({"name", "homepage_url"})

    site_editor_ids = fields.Many2many("res.users", string="Assigned website editors", groups="base.group_system")

    def _allows_site_editor(self) -> bool:
        self.ensure_one()
        return self.env.user in self.sudo().site_editor_ids

    def _check_assigned_sites(self) -> None:
        if not self or any(not site._allows_site_editor() for site in self):
            raise denied(self.env)

    def _site_editor_access(self) -> str | None:
        if is_site_editor(self.env):
            return "assigned" if self._allows_site_editor() else "unassigned"
        return None

    def write(self, vals: "odoo.values.website") -> bool:
        if is_site_editor(self.env):
            self._check_assigned_sites()
            if vals.keys() - self._site_editor_fields:
                raise denied(self.env)
        return super().write(vals)

    @api.model
    def action_site_editor_settings(self) -> dict[str, Any]:
        sites = self.sudo().search([("site_editor_ids", "in", [self.env.uid])])
        return {
            "type": "ir.actions.act_window",
            "name": self.env._("Assigned websites"),
            "res_model": "website",
            "views": [(self.env.ref("website_site_editor.settings_list").id, "list")],
            "domain": [("id", "in", sites.ids)],
        }

    def _render_template(self, template: str | int, values: dict[str, Any] | None = None) -> Any:
        if is_site_editor(self.env):
            self = self.with_context(inherit_branding=False, inherit_branding_auto=True)
        return super()._render_template(template, values)
