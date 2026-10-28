import base64
import logging
from dataclasses import dataclass
from time import monotonic
from typing import NamedTuple

import requests
from urllib3.util import Timeout

REQUEST_TIMEOUT_SECONDS = 5
BATCH_BUDGET_SECONDS = 20
DELIVERY_EXPIRY_SECONDS = 60
PAPER_TOLERANCE_TENTHS_MM = 15
DISCOVERY_PAGE_SIZE = 100
_logger = logging.getLogger(__name__)


class Rejected(Exception):
    pass


class Unconfirmed(Exception):
    pass


@dataclass(frozen=True)
class PreparedPrint:
    user_id: int
    printer_id: int
    printer_name: str
    title: str
    content: bytes
    content_type: str
    quantity: int
    paper: str | None
    commit_marker_id: int = 0


class PrintOutcome(NamedTuple):
    job: PreparedPrint
    state: str
    job_id: int | None = None


class PrintNodeClient:
    def __init__(self, api_key: str) -> None:
        self._api_key = api_key

    def _request(self, method: str, path: str, *, timeout: float = REQUEST_TIMEOUT_SECONDS, **kwargs: object) -> object:
        try:
            response = requests.request(
                method,
                f"https://api.printnode.com/{path}",
                auth=(self._api_key, ""),
                timeout=Timeout(total=timeout, connect=min(2, timeout), read=timeout),
                allow_redirects=False,
                **kwargs,
            )
        except requests.RequestException as error:
            raise Unconfirmed from error
        if 400 <= response.status_code < 500:
            raise Rejected(f"HTTP {response.status_code}")
        if not 200 <= response.status_code < 300:
            raise Unconfirmed
        try:
            return response.json()
        except ValueError as error:
            raise Unconfirmed from error

    def printers(self) -> list[dict]:
        printers = []
        after = 0
        while True:
            page = self._request("GET", "printers", params={"dir": "asc", "limit": DISCOVERY_PAGE_SIZE, "after": after})
            if not isinstance(page, list):
                raise Unconfirmed
            printers.extend(page)
            if len(page) < DISCOVERY_PAGE_SIZE:
                return printers
            next_after = max(printer["id"] for printer in page)
            if next_after <= after:
                raise Unconfirmed
            after = next_after

    def printer(self, printer_id: int) -> dict:
        printers = self._request("GET", f"printers/{printer_id}")
        if not isinstance(printers, list):
            raise Unconfirmed
        for printer in printers:
            if printer.get("id") == printer_id:
                return printer
        raise Rejected("missing printer")

    def submit(self, job: PreparedPrint, remaining: float) -> int:
        body = {
            "printerId": job.printer_id,
            "title": job.title,
            "contentType": f"{job.content_type}_base64",
            "content": base64.b64encode(job.content).decode(),
            "source": "Odoo",
            "qty": job.quantity,
            "expireAfter": DELIVERY_EXPIRY_SECONDS,
        }
        if job.paper is not None:
            body["options"] = {"paper": job.paper, "fit_to_page": False}
        job_id = self._request("POST", "printjobs", json=body, timeout=min(REQUEST_TIMEOUT_SECONDS, remaining))
        if type(job_id) is not int or job_id <= 0:
            raise Unconfirmed
        return job_id


def dispatch(client: PrintNodeClient, jobs: list[PreparedPrint]) -> list[PrintOutcome]:
    deadline = monotonic() + BATCH_BUDGET_SECONDS
    results = []
    for job in jobs:
        remaining = deadline - monotonic()
        if remaining <= 0:
            results.append(PrintOutcome(job, "unsent"))
            continue
        try:
            job_id = client.submit(job, remaining)
        except Rejected:
            results.append(PrintOutcome(job, "unsent"))
        except Exception:
            _logger.exception("Print submission unconfirmed for printer %s", job.printer_id)
            results.append(PrintOutcome(job, "unconfirmed"))
        else:
            results.append(PrintOutcome(job, "accepted", job_id))
    return results
