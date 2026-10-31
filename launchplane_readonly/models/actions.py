from typing import Any

from odoo import models


class IrActionsServer(models.Model):
    _inherit = "ir.actions.server"

    def run(self) -> Any:
        self._launchplane_readonly_refuse()
        return super().run()


class IrActionsReport(models.Model):
    _inherit = "ir.actions.report"

    def report_action(self, docids: Any, data: dict | None = None, config: bool = True) -> dict:
        self._launchplane_readonly_refuse()
        return super().report_action(docids, data=data, config=config)

    def _render(self, report_ref: Any, res_ids: list[int] | None = None, data: dict | None = None) -> Any:
        self._launchplane_readonly_refuse()
        return super()._render(report_ref, res_ids=res_ids, data=data)

    def _render_qweb_pdf(self, report_ref: Any, res_ids: list[int] | None = None, data: dict | None = None) -> Any:
        self._launchplane_readonly_refuse()
        return super()._render_qweb_pdf(report_ref, res_ids=res_ids, data=data)

    def _render_qweb_html(self, report_ref: Any, docids: list[int], data: dict | None = None) -> Any:
        self._launchplane_readonly_refuse()
        return super()._render_qweb_html(report_ref, docids, data=data)

    def _render_qweb_text(self, report_ref: Any, docids: list[int], data: dict | None = None) -> Any:
        self._launchplane_readonly_refuse()
        return super()._render_qweb_text(report_ref, docids, data=data)
