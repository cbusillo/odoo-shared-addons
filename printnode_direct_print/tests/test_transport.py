import base64
from dataclasses import replace
from unittest.mock import Mock, patch

import requests
from odoo.tests import TransactionCase, tagged

from .. import transport


@tagged("post_install", "-at_install")
class TestTransport(TransactionCase):
    def setUp(self) -> None:
        super().setUp()
        self.job = transport.PreparedPrint(2, 42, "Receiving", "Label", b"%PDF-fixture", "pdf", 2, "driver-label")
        self.client = transport.PrintNodeClient("inert-fixture")

    def test_pdf_request_uses_paper_no_scaling_one_quantity_and_expiry(self) -> None:
        with patch.object(requests, "request", return_value=Mock(status_code=201, json=lambda: 73)) as request:
            self.assertEqual(self.client.submit(self.job, transport.REQUEST_TIMEOUT_SECONDS), 73)
        _args, kwargs = request.call_args
        body = kwargs["json"]
        self.assertEqual(body["contentType"], "pdf_base64")
        self.assertEqual(base64.b64decode(body["content"]), self.job.content)
        self.assertEqual(body["qty"], self.job.quantity)
        self.assertEqual(body["expireAfter"], transport.DELIVERY_EXPIRY_SECONDS)
        self.assertEqual(body["options"]["paper"], self.job.paper)
        self.assertFalse(body["options"]["fit_to_page"])
        self.assertFalse(kwargs["allow_redirects"])
        self.assertLessEqual(kwargs["timeout"].total, transport.REQUEST_TIMEOUT_SECONDS)

    def test_raw_preserves_embedded_quantities_without_pdf_options(self) -> None:
        raw = replace(self.job, content=b"^XA^PQ7^XZ", content_type="raw", quantity=1, paper=None)
        with patch.object(requests, "request", return_value=Mock(status_code=201, json=lambda: 74)) as request:
            self.client.submit(raw, transport.REQUEST_TIMEOUT_SECONDS)
        body = request.call_args.kwargs["json"]
        self.assertEqual(body["contentType"], "raw_base64")
        self.assertEqual(base64.b64decode(body["content"]), raw.content)
        self.assertEqual(body["qty"], 1)
        self.assertNotIn("options", body)

    def test_rejection_and_uncertain_effects_are_distinct_and_never_retried(self) -> None:
        for response, error in [
            (Mock(status_code=400), transport.Rejected),
            (Mock(status_code=503), transport.Unconfirmed),
            (Mock(status_code=302), transport.Unconfirmed),
            (Mock(status_code=201, json=lambda: None), transport.Unconfirmed),
        ]:
            with self.subTest(response=response), patch.object(requests, "request", return_value=response) as request:
                with self.assertRaises(error):
                    self.client.submit(self.job, transport.REQUEST_TIMEOUT_SECONDS)
                self.assertEqual(request.call_count, 1)
        with patch.object(requests, "request", side_effect=requests.Timeout) as request:
            with self.assertRaises(transport.Unconfirmed):
                self.client.submit(self.job, transport.REQUEST_TIMEOUT_SECONDS)
            self.assertEqual(request.call_count, 1)

    def test_mixed_batch_keeps_early_failure_and_reports_budget_exhaustion(self) -> None:
        client = Mock()
        client.submit.side_effect = [transport.Rejected(), 73, transport.Unconfirmed()]
        start = 10.0

        def clock() -> float:
            return start + transport.BATCH_BUDGET_SECONDS if client.submit.call_count >= 3 else start

        with patch.object(transport, "monotonic", side_effect=clock):
            results = transport.dispatch(client, [self.job] * 4)
        self.assertEqual([result[1] for result in results], ["unsent", "accepted", "unconfirmed", "unsent"])
        self.assertEqual(client.submit.call_count, 3)
        self.assertEqual(results[1][2], 73)

    def test_unexpected_failure_does_not_hide_other_jobs(self) -> None:
        client = Mock()
        client.submit.side_effect = [ValueError("fixture"), 74]
        results = transport.dispatch(client, [self.job, self.job])
        self.assertEqual([result[1] for result in results], ["unconfirmed", "accepted"])

    def test_discovery_includes_more_than_one_page(self) -> None:
        first = [{"id": index} for index in range(1, transport.DISCOVERY_PAGE_SIZE + 1)]
        last = [{"id": transport.DISCOVERY_PAGE_SIZE + 1}]
        with patch.object(self.client, "_request", side_effect=[first, last]) as request:
            self.assertEqual(self.client.printers(), first + last)
        self.assertEqual(request.call_count, 2)
