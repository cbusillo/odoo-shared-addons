from typing import Any

from odoo.addons.bus.controllers.websocket import WebsocketController
from odoo.http import request, route


class ReadOnlyWorkerBundle(WebsocketController):
    def _readonly_worker_bundle(self, rule: Any, args: dict) -> bool:
        return request.env["base"]._launchplane_readonly_actor()

    @route(readonly=_readonly_worker_bundle)
    def get_websocket_worker_bundle(self, v: str | None = None) -> Any:
        return super().get_websocket_worker_bundle(v=v)
