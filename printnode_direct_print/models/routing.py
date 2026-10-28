import logging
from collections import defaultdict
from uuid import uuid4

from odoo import SUPERUSER_ID, api, models
from odoo.exceptions import AccessError, UserError
from odoo.http import request

from ..transport import PAPER_TOLERANCE_TENTHS_MM, PreparedPrint, PrintNodeClient, PrintOutcome, Rejected, Unconfirmed, dispatch
from .printers import physical_size

_logger = logging.getLogger(__name__)
BATCH_KEY = "printnode_direct_print.batch"


def take_committed_batch(registry: object, jobs: list[PreparedPrint]) -> list[PreparedPrint]:
    with registry.cursor() as cursor:
        cursor.execute("SET LOCAL statement_timeout = '3s'")
        env = api.Environment(cursor, jobs[0].user_id, {})
        markers = env["bus.bus"].sudo().browse([job.commit_marker_id for job in jobs]).exists()
        surviving = set(markers.ids)
        pending = [job for job in jobs if job.commit_marker_id in surviving]
        if not pending:
            return []
        markers.unlink()
        cursor.commit()
        return pending


def notify_results(registry: object, user_id: int, results: list[PrintOutcome]) -> None:
    with registry.cursor() as cursor:
        cursor.execute("SET LOCAL statement_timeout = '3s'")
        env = api.Environment(cursor, user_id, {})
        env = env(context={"lang": env.user.lang})
        messages = []
        failed = False
        for job, status, job_id in results:
            if status == "accepted":
                messages.append(
                    env._("Sent %(title)s to %(printer)s (job %(job)s).", title=job.title, printer=job.printer_name, job=job_id)
                )
            elif status == "unsent":
                failed = True
                messages.append(env._("%(title)s was not submitted to %(printer)s.", title=job.title, printer=job.printer_name))
            else:
                failed = True
                messages.append(
                    env._(
                        "Delivery of %(title)s to %(printer)s is unconfirmed. Check the printer before printing again.",
                        title=job.title,
                        printer=job.printer_name,
                    )
                )
        env.user._bus_send(
            "simple_notification",
            {
                "title": env._("Printing"),
                "message": "\n".join(messages),
                "type": "warning" if failed else "success",
                "sticky": failed,
            },
        )
        cursor.commit()


def dispatch_batch(registry: object, jobs: list[PreparedPrint]) -> None:
    if not jobs:
        return
    try:
        pending = take_committed_batch(registry, jobs)
    except Exception:
        _logger.exception("Committed prints could not be verified; no submissions attempted")
        return
    if not pending:
        return
    try:
        with registry.cursor() as cursor:
            cursor.execute("SET LOCAL statement_timeout = '3s'")
            client = api.Environment(cursor, pending[0].user_id, {})["printnode.routing"]._client()
    except Exception:
        _logger.exception("Print batch could not dispatch after commit")
        results = [PrintOutcome(job, "unsent") for job in pending]
    else:
        try:
            results = dispatch(client, pending)
        except Exception:
            _logger.exception("Print batch completion is unconfirmed")
            results = [PrintOutcome(job, "unconfirmed") for job in pending]
    grouped = defaultdict(list)
    for result in results:
        grouped[result.job.user_id].append(result)
        if result.state != "accepted":
            _logger.warning("Print delivery %s for user %s, printer %s", result.state, result.job.user_id, result.job.printer_id)
    for user_id, user_results in grouped.items():
        try:
            notify_results(registry, user_id, user_results)
        except Exception:
            _logger.exception("Print delivery notification failed for user %s", user_id)


class PrintNodeRouting(models.AbstractModel):
    _name = "printnode.routing"
    _description = "Printer routing"

    def _check_actor(self) -> None:
        if self.env.uid == SUPERUSER_ID or not self.env.user._is_internal() or self.env.context.get("cron_id"):
            raise AccessError(self.env._("Printing needs the signed-in person. Open My printers in your own account."))
        if request and request.params.get("method") in ("onchange", "onchange_batch"):
            raise UserError(self.env._("Save the record before printing. Nothing was submitted."))

    def _client(self) -> PrintNodeClient:
        key = self.env["ir.config_parameter"].sudo().get_param("printnode.api_key")
        if not key:
            raise UserError(self.env._("PrintNode is not configured. Ask your administrator to configure printing."))
        return PrintNodeClient(key)

    def _resolve_printer(self, paperformat: "odoo.model.report_paperformat") -> "odoo.model.printnode_printer":
        self._check_actor()
        width, height = physical_size(paperformat)
        preference = (
            self.env["printnode.preference"]
            .sudo()
            .search(
                [
                    ("user_id", "=", self.env.uid),
                    ("width", "=", width),
                    ("height", "=", height),
                ],
                limit=1,
            )
        )
        if not preference:
            raise UserError(
                self.env._(
                    "No printer set for %(width)s × %(height)s mm. Open My printers to choose one.",
                    width=f"{width / 10:g}",
                    height=f"{height / 10:g}",
                )
            )
        return preference.printer_id

    def _preflight(self, paperformat: "odoo.model.report_paperformat", content_type: str) -> tuple[dict, str | None]:
        selected = self._resolve_printer(paperformat)
        printers = self.env.cr.postcommit.data.setdefault("printnode_direct_print.printers", {})
        try:
            if selected.external_id not in printers:
                printers[selected.external_id] = self._client().printer(selected.external_id)
            printer = printers[selected.external_id]
        except (Rejected, Unconfirmed) as error:
            raise UserError(
                self.env._(
                    "Cannot reach %(printer)s. Nothing was submitted. Check My printers and try again.", printer=selected.name
                )
            ) from error
        if printer.get("state") != "online" or printer.get("computer", {}).get("state") != "connected":
            raise UserError(self.env._("%(printer)s is offline. Nothing was submitted.", printer=selected.name))
        paper = self._matching_paper(printer, paperformat) if content_type == "pdf" else None
        return printer, paper

    def _matching_paper(self, printer: dict, paperformat: "odoo.model.report_paperformat") -> str:
        size = physical_size(paperformat)
        papers = (printer.get("capabilities") or {}).get("papers") or {}
        matches = []
        for name, dimensions in papers.items():
            if not dimensions or len(dimensions) != 2 or not all(dimensions):
                continue
            difference = max(abs(a - b) for a, b in zip(sorted(dimensions), size, strict=True))
            if difference <= PAPER_TOLERANCE_TENTHS_MM:
                matches.append((difference, name))
        if matches:
            return min(matches)[1]
        raise UserError(
            self.env._(
                "%(printer)s has no matching %(width)s × %(height)s mm paper size. Nothing was submitted.",
                printer=printer["name"],
                width=f"{size[0] / 10:g}",
                height=f"{size[1] / 10:g}",
            )
        )

    def _prepare_print(
        self, content: bytes, paperformat: "odoo.model.report_paperformat", *, content_type: str, title: str, quantity: int = 1
    ) -> dict:
        if content_type not in ("pdf", "raw") or not isinstance(content, bytes) or not content:
            raise UserError(self.env._("Printing needs nonempty PDF or raw document bytes and an explicit content type."))
        if type(quantity) is not int or quantity < 1 or quantity > 100 or (content_type == "raw" and quantity != 1):
            raise UserError(self.env._("Choose 1 to 100 PDF copies. Raw labels must contain their own quantities."))
        if content_type == "pdf" and not content.startswith(b"%PDF-"):
            raise UserError(self.env._("The rendered document is not a PDF. Nothing was submitted."))
        if content_type == "raw" and content.startswith(b"%PDF-"):
            raise UserError(self.env._("PDF documents must use PDF transport. Nothing was submitted."))
        printer, paper = self._preflight(paperformat, content_type)
        marker = self.env["bus.bus"].sudo().create({"channel": f"printnode_direct_print.{uuid4().hex}", "message": "{}"})
        job = PreparedPrint(self.env.uid, printer["id"], printer["name"], title, content, content_type, quantity, paper, marker.id)
        callbacks = self.env.cr.postcommit
        if BATCH_KEY not in callbacks.data:
            jobs = callbacks.data[BATCH_KEY] = []
            registry = self.env.registry
            callbacks.add(lambda: dispatch_batch(registry, jobs))
        callbacks.data[BATCH_KEY].append(job)
        return {"state": "prepared", "printer": printer["name"]}
