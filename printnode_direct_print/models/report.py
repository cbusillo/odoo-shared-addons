from typing import NamedTuple

from odoo import fields, models
from odoo.exceptions import AccessError, UserError


class AuthorizedPrint(NamedTuple):
    report: "odoo.model.ir_actions_report"
    record_ids: list[int] | None
    data: dict


class IrActionsReport(models.Model):
    _inherit = "ir.actions.report"

    printnode_direct = fields.Boolean("Print through personal printer", groups="base.group_user")

    def _get_readable_fields(self) -> set[str]:
        return super()._get_readable_fields() | {"printnode_direct"}

    def report_action(
        self, docids: "odoo.model.base | list[int] | int | None", data: dict | None = None, config: bool = True
    ) -> dict:
        action = super().report_action(docids, data, config)
        if action.get("type") == "ir.actions.report" and self.printnode_direct:
            action.update(id=self.id, printnode_direct=True)
        return action

    def _authorized_print(self, res_ids: list[int] | None, data: dict | None) -> AuthorizedPrint:
        self.ensure_one()
        self.env["printnode.routing"]._check_actor()
        report = self.sudo(False)
        if not report.env.companies:
            raise AccessError(self.env._("Choose an allowed company before printing."))
        report.check_access("read")
        if not report.printnode_direct or report.report_type != "qweb-pdf":
            raise UserError(self.env._("%(report)s is not enabled for direct PDF printing.", report=report.name))
        if report.group_ids and not (report.group_ids & report.env.user.all_group_ids):
            raise AccessError(self.env._("You do not have access to this report."))
        if data is not None and not isinstance(data, dict):
            raise UserError(self.env._("Report data must be a mapping."))
        res_ids = None if data else (res_ids or [])
        if res_ids is not None and (
            not isinstance(res_ids, list) or any(type(record_id) is not int or record_id <= 0 for record_id in res_ids)
        ):
            raise UserError(self.env._("Choose the records to print."))
        records = report.env[report.model].browse(res_ids or [])
        records.check_access("read")
        if set(records.exists().ids) != set(res_ids or []):
            raise AccessError(self.env._("Some records are no longer available."))
        clean_context = {
            key: value
            for key, value in report.env.context.items()
            if key in ("lang", "tz", "allowed_company_ids", "force_report_rendering")
        }
        clean_context.update(active_model=report.model, active_ids=res_ids or [], active_id=res_ids[0] if res_ids else False)
        report = report.with_context(clean_context)
        report_data = report._printnode_validate_data(dict(data or {}))
        if not res_ids and not report_data:
            raise UserError(self.env._("Choose the records to print."))
        return AuthorizedPrint(report, res_ids, report_data)

    def _printnode_validate_data(self, data: dict) -> dict:
        if data:
            raise UserError(
                self.env._("This report needs a validated print-data adapter before direct printing with wizard options.")
            )
        return data

    def _prepare_report_print(self, res_ids: list[int] | None = None, data: dict | None = None, *, quantity: int = 1) -> dict:
        report, record_ids, report_data = self._authorized_print(res_ids, data)
        routing = report.env["printnode.routing"]
        paper = report.get_paperformat()
        pdf, _report_type = report._render_qweb_pdf(report, res_ids=record_ids, data=report_data)
        return routing._prepare_print(pdf, paper, content_type="pdf", title=report.name, quantity=quantity)

    def printnode_print(self, res_ids: list[int] | None = None, data: dict | None = None) -> dict:
        return self._prepare_report_print(res_ids, data)
