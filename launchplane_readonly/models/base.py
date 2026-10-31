from contextvars import ContextVar
from typing import Any

from odoo import api, models
from odoo.exceptions import AccessError

from ..policy import GROUP

AUTHENTICATING = ContextVar("launchplane_readonly_authenticating", default=False)


class Base(models.AbstractModel):
    _inherit = "base"

    def _launchplane_readonly_actor(self) -> bool:
        if not self.env.uid or self.env.uid <= 2:
            return False
        user = self.env.user.sudo()
        return bool(user.launchplane_readonly_owner or user.has_group(GROUP))

    def _launchplane_readonly_refuse(self) -> None:
        if self._launchplane_readonly_actor():
            raise AccessError(self.env._("This test identity can only read records."))

    @api.model_create_multi
    def create(self, vals_list: list[dict[str, Any]]) -> "odoo.model.base":
        if not (AUTHENTICATING.get() and self._name == "res.users.log" and all(not values for values in vals_list)):
            self._launchplane_readonly_refuse()
        return super().create(vals_list)

    def write(self, values: dict[str, Any]) -> bool:
        if not (AUTHENTICATING.get() and self._name == "res.users" and self.ids == [self.env.uid] and set(values) <= {"tz"}):
            self._launchplane_readonly_refuse()
        return super().write(values)

    @api.ondelete(at_uninstall=True)
    def _launchplane_readonly_deny_delete(self) -> None:
        self._launchplane_readonly_refuse()

    @api.private
    def with_user(self, user: Any) -> "odoo.model.base":
        if self._launchplane_readonly_actor() and user and getattr(user, "id", user) != self.env.uid:
            self._launchplane_readonly_refuse()
        return super().with_user(user)
