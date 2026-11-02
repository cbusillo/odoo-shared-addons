from typing import Any

from odoo.addons.mail.controllers.webclient import WebclientController
from odoo.addons.mail.models.mail_message import SHARE_DOMAIN
from odoo.addons.mail.tools.discuss import Store
from odoo.addons.mail.tools.store_handler import store_handler_registry
from odoo.fields import Domain
from odoo.http import request


class ReadOnlyWebclientController(WebclientController):
    def _is_mail_fetch_readonly(self) -> bool:
        if request.httprequest.method == "OPTIONS" or not request.env["base"]._launchplane_readonly_actor():
            return super()._is_mail_fetch_readonly()
        fetch_params = request.get_json_data().get("params", {}).get("fetch_params", [])
        for fetch_param in fetch_params:
            name, _, _ = store_handler_registry._parse_fetch_param(fetch_param)
            if name == "/mail/thread/messages":
                entry = store_handler_registry._items.get(name)
                handler = getattr(self, entry.func_name, None) if entry else None
                if getattr(handler, "__func__", None) is not READONLY_THREAD_MESSAGES:
                    return False
            elif not store_handler_registry.is_fetch_readonly([fetch_param]):
                return False
        return True

    def store_get_thread_messages(
        self,
        store: Store,
        thread_model: str,
        thread_id: int,
        fetch_params: dict | None = None,
        access_params: dict | None = None,
    ) -> Any:
        if not request.env["base"]._launchplane_readonly_actor():
            return super().store_get_thread_messages(store, thread_model, thread_id, fetch_params, access_params)
        request.update_context(add_chatter_fields=True)
        if thread := self._get_thread_with_access(thread_model, thread_id, mode="read", **(access_params or {})):
            domain = Domain.TRUE
            if not request.env.user._is_internal() or not thread.sudo(False).has_access("read"):
                domain = (
                    SHARE_DOMAIN
                    & Domain("message_type", "in", thread._get_customer_portal_message_types())
                    & ~request.env["mail.message"]._get_empty_domain()
                )
            self._resolve_messages(store, domain=domain, thread=thread, fetch_params=fetch_params, sudo=thread.env.su)


READONLY_THREAD_MESSAGES = ReadOnlyWebclientController.store_get_thread_messages
