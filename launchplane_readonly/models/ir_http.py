from collections.abc import Callable
from contextlib import nullcontext
from functools import partial
from typing import Any

from odoo import models, sql_db
from odoo.addons.web.controllers.dataset import DataSet
from odoo.addons.web.controllers.export import Export, ExportFormat
from odoo.addons.web.controllers.home import Home
from odoo.addons.web.controllers.report import ReportController
from odoo.addons.web.models.models import Base as WebBase
from odoo.exceptions import AccessError
from odoo.http import request
from odoo.http.session import SessionExpiredException, logout
from psycopg2.errors import ReadOnlySqlTransaction

from ..policy import matches_native_read
from .base import STAFF_OBSERVER_READ_CURSOR

NATIVE_CALL_KW = DataSet.call_kw
NATIVE_RANGE_READ = WebBase.search_panel_select_range
NATIVE_RANGE_HELPERS = (
    WebBase._search_panel_field_image,
    WebBase._search_panel_domain_image,
    WebBase._search_panel_sanitized_parent_hierarchy,
    WebBase._search_panel_global_counters,
    WebBase._search_panel_selection_range,
)


class IrHttp(models.AbstractModel):
    _inherit = "ir.http"

    @classmethod
    def _pre_dispatch(cls, rule: Any, args: dict) -> Any:
        base = request.env["base"]
        actors = base._launchplane_readonly_users()
        if actors:
            try:
                for user in actors:
                    user._launchplane_readonly_check_session()
            except (AccessError, ValueError, TypeError) as error:
                logout(request.session, keep_db=True)
                raise SessionExpiredException() from error

        staff_modes = base._staff_observer_modes()
        exclusive = bool(actors) or "observer" in staff_modes
        if exclusive or (staff_modes and not getattr(request, "_staff_observer_retry", False)):
            controller = rule.endpoint.func.__self__
            path = request.httprequest.path
            prohibited = isinstance(controller, (ReportController, Export, ExportFormat)) or path.startswith(
                ("/web/action/run", "/base_import")
            )
            if exclusive and prohibited:
                base._readonly_business_refuse()
            bootstrap = rule.endpoint.func.__name__ == "web_client" and isinstance(controller, Home)
            if not prohibited and (cls._readonly_route(rule, args) or (exclusive and bootstrap)):
                request.dispatcher.dispatch = partial(
                    cls._launchplane_readonly_dispatch, request.dispatcher.dispatch, staff_overlay=not exclusive
                )
            elif exclusive:
                cls._readonly_action_refusal()
        return super()._pre_dispatch(rule, args)

    @classmethod
    def _readonly_route(cls, rule: Any, args: dict) -> bool:
        controller = rule.endpoint.func.__self__
        readonly = rule.endpoint.routing.get("readonly", False)
        if callable(readonly):
            readonly = readonly(controller, rule, args)
        if isinstance(controller, DataSet):
            params = request.get_json_data()["params"]
            if params["method"] == NATIVE_RANGE_READ.__name__:
                readonly = getattr(rule.endpoint.func, "__func__", None) is NATIVE_CALL_KW and matches_native_read(
                    request.env.registry[params["model"]], params["method"], NATIVE_RANGE_READ, NATIVE_RANGE_HELPERS
                )
        return readonly

    @classmethod
    def _launchplane_readonly_cursor(cls) -> Any:
        cursor = request.env.registry.cursor(readonly=True)
        if cursor.readonly:
            return cursor
        cursor.close()
        return sql_db.db_connect(request.env.cr.dbname, readonly=True).cursor()

    @classmethod
    def _dispatch(cls, endpoint: Any) -> Any:
        return cls._launchplane_readonly_call(super()._dispatch, endpoint)

    @classmethod
    def _post_dispatch(cls, response: Any) -> Any:
        return cls._launchplane_readonly_call(super()._post_dispatch, response)

    @classmethod
    def _serve_fallback(cls) -> Any:
        if request.env["base"]._readonly_business_actor():
            cls._readonly_action_refusal()
        return super()._serve_fallback()

    @classmethod
    def _readonly_action_refusal(cls) -> None:
        if request.env["base"]._launchplane_readonly_actor():
            raise AccessError(request.env._("This test identity cannot use this action."))
        raise AccessError(request.env._("This staff role cannot use this action."))

    @classmethod
    def _handle_error(cls, exception: Exception) -> Any:
        return cls._launchplane_readonly_call(super()._handle_error, exception)

    @classmethod
    def _launchplane_readonly_dispatch(cls, operation: Callable[..., Any], endpoint: Any, args: dict, *, staff_overlay: bool) -> Any:
        request.dispatcher.dispatch = operation

        def dispatch() -> Any:
            values = {
                key: value.with_env(request.env) if isinstance(value, models.BaseModel) else value for key, value in args.items()
            }
            return operation(endpoint, values)

        try:
            return cls._launchplane_readonly_call(dispatch, staff_overlay=staff_overlay)
        except ReadOnlySqlTransaction:
            request._staff_observer_retry = True
            if request.env.cr.readonly:
                raise
            return dispatch()

    @classmethod
    def _launchplane_readonly_call(cls, operation: Callable[..., Any], *args: Any, staff_overlay: bool = False) -> Any:
        if not staff_overlay and not request.env["base"]._readonly_business_actor():
            return operation(*args)
        original = request.env
        manager = nullcontext(original.cr) if original.cr.readonly else cls._launchplane_readonly_cursor()
        cursor = None
        read_scope = None
        try:
            with manager as cursor:
                request.env = original(cr=cursor)
                if staff_overlay:
                    read_scope = STAFF_OBSERVER_READ_CURSOR.set(cursor)
                result = operation(*args)
                cursor.flush()
                return result
        except ReadOnlySqlTransaction as error:
            if staff_overlay:
                raise
            if cursor is not None and not cursor.closed:
                cursor.rollback()
            message = (
                original._("This test identity cannot change database records.")
                if original["base"]._launchplane_readonly_actor()
                else original._("This read-only session cannot change database records.")
            )
            raise AccessError(message) from error
        finally:
            if read_scope is not None:
                STAFF_OBSERVER_READ_CURSOR.reset(read_scope)
            request.env = original
