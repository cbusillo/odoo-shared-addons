import json
from contextvars import ContextVar
from typing import Any

from odoo import SUPERUSER_ID, api, models
from odoo.exceptions import AccessError
from odoo.http import request

from ..policy import GROUP

AUTHENTICATING = ContextVar("launchplane_readonly_authenticating", default=False)
SERVING_STAFF_ASSETS = ContextVar("serving_staff_assets", default=False)
STAFF_OBSERVER_READ_CURSOR: ContextVar[object | None] = ContextVar("staff_observer_read_cursor", default=None)


class Base(models.AbstractModel):
    _inherit = "base"

    def _readonly_request_users(self) -> "odoo.model.res_users":
        actor_ids = {self.env.uid}
        if request:
            actor_ids.add(request.session.uid)
        actors = self.env["res.users"].sudo().browse([])
        for uid in actor_ids - {None, False, 1, 2}:
            user = self.env.user.sudo() if uid == self.env.uid else self.env["res.users"].sudo().browse(uid).exists()
            actors |= user
        return actors

    def _launchplane_readonly_users(self) -> "odoo.model.res_users":
        return self._readonly_request_users().filtered(lambda user: user.launchplane_readonly_owner or user.has_group(GROUP))

    def _staff_observer_modes(self) -> set[str]:
        return {mode for user in self._readonly_request_users() if (mode := user._staff_observer_mode())}

    def _readonly_business_actor(self) -> bool:
        return self._launchplane_readonly_actor() or "observer" in self._staff_observer_modes()

    def _launchplane_readonly_actor(self) -> bool:
        return bool(self._launchplane_readonly_users())

    def _launchplane_readonly_refuse(self) -> None:
        if self._launchplane_readonly_actor():
            raise AccessError(self.env._("This test identity can only read records."))

    def _readonly_business_refuse(self) -> None:
        self._launchplane_readonly_refuse()
        if "observer" in self._staff_observer_modes():
            raise AccessError(self.env._("This staff role can only read business records."))

    def _creating_staff_assets(self, vals_list: list[dict[str, Any]]) -> bool:
        if not SERVING_STAFF_ASSETS.get():
            return False
        if self._name == "bus.bus":
            return all(json.loads(values["message"]).get("type") == "bundle_changed" for values in vals_list)
        return (
            self._name == "ir.attachment"
            and self.env.uid == SUPERUSER_ID
            and all(
                values.get("public")
                and values.get("type") == "binary"
                and values.get("res_model") == "ir.ui.view"
                and not values.get("res_id")
                and (values.get("url") or "").startswith("/web/assets/")
                for values in vals_list
            )
        )

    @api.model_create_multi
    def create(self, vals_list: list[dict[str, Any]]) -> "odoo.model.base":
        if AUTHENTICATING.get() and self._name == "res.users.log" and all(not values for values in vals_list):
            return super().create(vals_list)
        if self._creating_staff_assets(vals_list):
            self._launchplane_readonly_refuse()
        else:
            self._readonly_business_refuse()
        return super().create(vals_list)

    def write(self, values: dict[str, Any]) -> bool:
        own_timezone = set(values) <= {"tz"} and (
            (self._name == "res.users" and self.ids == [self.env.uid])
            or (self._name == "res.partner" and self == self.env.user.partner_id)
        )
        if not (AUTHENTICATING.get() and own_timezone):
            self._readonly_business_refuse()
        return super().write(values)

    @api.ondelete(at_uninstall=True)
    def _launchplane_readonly_deny_delete(self) -> None:
        self._readonly_business_refuse()
