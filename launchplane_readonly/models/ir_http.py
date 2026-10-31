from typing import Any

from odoo import api, models, sql_db
from odoo.addons.web.controllers.export import Export, ExportFormat
from odoo.addons.web.controllers.home import Home
from odoo.addons.web.controllers.report import ReportController
from odoo.exceptions import AccessError
from odoo.http import request
from odoo.http.session import SessionExpiredException, logout
from psycopg2.errors import ReadOnlySqlTransaction

from ..policy import GROUP


class IrHttp(models.AbstractModel):
    _inherit = "ir.http"

    @classmethod
    def _launchplane_readonly_request(cls) -> bool:
        return request.env["base"]._launchplane_readonly_actor()

    @classmethod
    def _pre_dispatch(cls, rule: Any, args: dict) -> Any:
        if cls._launchplane_readonly_request():
            try:
                for uid in {request.session.uid, request.env.uid} - {None, False, 1, 2}:
                    user = request.env["res.users"].sudo().browse(uid).exists()
                    if user and (user.launchplane_readonly_owner or user.has_group(GROUP)):
                        user._launchplane_readonly_check_session()
            except (AccessError, ValueError, TypeError) as error:
                logout(request.session, keep_db=True)
                raise SessionExpiredException() from error
            path = request.httprequest.path
            controller = rule.endpoint.func.__self__
            if isinstance(controller, (ReportController, Export, ExportFormat)) or path.startswith(
                ("/web/action/run", "/base_import", "/web/dataset/call_button")
            ):
                raise AccessError(request.env._("This test identity can only read records."))
            readonly = rule.endpoint.routing.get("readonly", False)
            if callable(readonly):
                readonly = readonly(rule.endpoint.func.__self__, rule, args)
            bootstrap = rule.endpoint.func.__name__ == "web_client" and isinstance(controller, Home)
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
                try:
                    result = super()._dispatch(endpoint)
                    request.env.flush_all()
                    return result
                except ReadOnlySqlTransaction as error:
                    raise AccessError(original._("This test identity cannot change database records.")) from error
            finally:
                request.env = original
