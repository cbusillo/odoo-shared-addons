from typing import Any

from odoo import api, models, sql_db
from odoo.exceptions import AccessError
from odoo.http import request


class IrHttp(models.AbstractModel):
    _inherit = "ir.http"

    @classmethod
    def _launchplane_readonly_request(cls) -> bool:
        return any(
            uid and request.env["res.users"].with_user(uid)._launchplane_readonly_actor()
            for uid in {request.session.uid, request.env.uid}
        )

    @classmethod
    def _pre_dispatch(cls, rule: Any, args: dict) -> Any:
        if cls._launchplane_readonly_request():
            for uid in {request.session.uid, request.env.uid} - {None, False}:
                user = request.env["res.users"].with_user(uid).browse(uid)
                if user._launchplane_readonly_actor():
                    user._launchplane_readonly_check_session()
            path = request.httprequest.path
            if path.startswith(("/report/", "/web/export", "/web/action/run", "/base_import", "/web/dataset/call_button")):
                raise AccessError(request.env._("This test identity can only read records."))
            readonly = rule.endpoint.routing.get("readonly", False)
            if callable(readonly):
                readonly = readonly(rule.endpoint.func.__self__, rule, args)
            bootstrap = (
                rule.endpoint.func.__name__ == "web_client" and rule.endpoint.func.__module__ == "odoo.addons.web.controllers.home"
            )
            if not (readonly or bootstrap):
                raise AccessError(request.env._("This test identity cannot use this action."))
        return super()._pre_dispatch(rule, args)

    @classmethod
    def _dispatch(cls, endpoint: Any) -> Any:
        if not cls._launchplane_readonly_request():
            return super()._dispatch(endpoint)
        original = request.env
        with sql_db.db_connect(original.cr.dbname, readonly=True).cursor() as cursor:
            request.env = api.Environment(cursor, original.uid, original.context, su=original.su)
            try:
                result = super()._dispatch(endpoint)
                request.env.flush_all()
                return result
            finally:
                request.env = original
