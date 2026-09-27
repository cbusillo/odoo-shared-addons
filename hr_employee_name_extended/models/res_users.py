from odoo import models


class ResUsers(models.Model):
    _name = "res.users"
    _inherit = ["res.users", "hr.name.sync.mixin"]

    def write(self, vals: "odoo.values.res_users") -> bool:
        users = self
        if "name" in vals and not self.env.context.get("allow_employee_sync"):
            # Odoo's hr module copies a user's new name onto the employee; keep
            # the employee's name parts unless the caller opts in.
            users = self.with_context(keep_employee_name=True)
        res = super(ResUsers, users).write(vals)
        if "name" in vals and self.env.context.get("allow_employee_sync") and not self.env.context.get("skip_employee_sync"):
            self._sync_name_to_employees(vals["name"])
        return res

    def _sync_name_to_employees(self, new_name: str) -> None:
        domain = [("user_id", "in", self.ids)]
        self._sync_name_to_employees_common(new_name, domain)
