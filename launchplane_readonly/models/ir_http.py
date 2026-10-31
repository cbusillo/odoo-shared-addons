from contextlib import nullcontext
from typing import Any

from odoo import models, sql_db
from odoo.addons.web.controllers.export import Export, ExportFormat
from odoo.addons.web.controllers.home import Home
from odoo.addons.web.controllers.report import ReportController
from odoo.exceptions import AccessError
from odoo.http import request
from odoo.http.session import SessionExpiredException, logout
from psycopg2.errors import ReadOnlySqlTransaction


class IrHttp(models.AbstractModel):
    _inherit = "ir.http"

    @classmethod
    def _pre_dispatch(cls, rule: Any, args: dict) -> Any:
        actors = request.env["base"]._launchplane_readonly_users()
        if actors:
            try:
                for user in actors:
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
    def _launchplane_readonly_cursor(cls) -> Any:
        cursor = request.env.registry.cursor(readonly=True)
        if cursor.readonly:
            return cursor
        cursor.close()
        return sql_db.db_connect(request.env.cr.dbname, readonly=True).cursor()

    @classmethod
    def _dispatch(cls, endpoint: Any) -> Any:
        if not request.env["base"]._launchplane_readonly_actor():
            return super()._dispatch(endpoint)
        original = request.env
        manager = nullcontext(original.cr) if original.cr.readonly else cls._launchplane_readonly_cursor()
        with manager as cursor:
            request.env = original(cr=cursor)
            try:
                try:
                    result = super()._dispatch(endpoint)
                    request.env.flush_all()
                    return result
                except ReadOnlySqlTransaction as error:
                    cursor.rollback()
                    raise AccessError(original._("This test identity cannot change database records.")) from error
            finally:
                request.env = original
