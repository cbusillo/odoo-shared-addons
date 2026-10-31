from contextvars import ContextVar
from typing import Any

from odoo import api, models
from odoo.exceptions import AccessError
from odoo.http import request

from ..policy import GROUP

AUTHENTICATING = ContextVar("launchplane_readonly_authenticating", default=False)


class Base(models.AbstractModel):
    _inherit = "base"

    def _launchplane_readonly_actor(self) -> bool:
        actor_ids = {self.env.uid}
        if request:
            actor_ids.add(request.session.uid)
        for uid in actor_ids - {None, False, 1, 2}:
            user = self.env["res.users"].sudo().browse(uid).exists()
            if user and (user.launchplane_readonly_owner or user.has_group(GROUP)):
                return True
        return False

    def _launchplane_readonly_refuse(self) -> None:
        if self._launchplane_readonly_actor():
            raise AccessError(self.env._("This test identity can only read records."))

    @api.model_create_multi
    def create(self, vals_list: list[dict[str, Any]]) -> "odoo.model.base":
        if not (AUTHENTICATING.get() and self._name == "res.users.log" and all(not values for values in vals_list)):
            self._launchplane_readonly_refuse()
        return super().create(vals_list)

    def write(self, values: dict[str, Any]) -> bool:
        own_timezone = set(values) <= {"tz"} and (
            (self._name == "res.users" and self.ids == [self.env.uid])
            or (self._name == "res.partner" and self == self.env.user.partner_id)
        )
        if not (AUTHENTICATING.get() and own_timezone):
            self._launchplane_readonly_refuse()
        return super().write(values)

    @api.ondelete(at_uninstall=True)
    def _launchplane_readonly_deny_delete(self) -> None:
        self._launchplane_readonly_refuse()
