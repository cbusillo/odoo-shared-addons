from dataclasses import replace
from io import BytesIO
from unittest.mock import Mock, patch

from odoo import Command, api
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests import TransactionCase, tagged
from odoo.tools.pdf import PdfReader

from .. import transport
from ..models import routing
from ..models.printers import physical_size


@tagged("post_install", "-at_install")
class TestRouting(TransactionCase):
    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.admin = cls.env.ref("base.user_admin")
        cls.people = (
            cls.env["res.users"]
            .with_context(no_reset_password=True)
            .create(
                [
                    {"name": name, "login": f"print-fixture-{name}", "group_ids": [Command.set([cls.env.ref("base.group_user").id])]}
                    for name in ("one", "two")
                ]
            )
        )
        cls.paper = cls.env["report.paperformat"].create(
            {"name": "Fixture label", "format": "custom", "page_width": 50, "page_height": 25}
        )
        cls.alias = cls.env["report.paperformat"].create(
            {"name": "Alias label", "format": "custom", "page_width": 25, "page_height": 50}
        )
        cls.letter = cls.env["report.paperformat"].create({"name": "Named Letter", "format": "Letter"})
        cls.printers = cls.env["printnode.printer"].create(
            [{"external_id": 42 + index, "name": f"Fixture {index}"} for index in range(2)]
        )
        cls.report = cls.env["ir.actions.report"].create(
            {
                "name": "Fixture report",
                "model": "res.partner",
                "report_type": "qweb-pdf",
                "report_name": "printnode_direct_print.fixture",
                "paperformat_id": cls.paper.id,
                "printnode_direct": True,
            }
        )

    def setUp(self) -> None:
        super().setUp()
        self.service = self.env["printnode.routing"].with_user(self.people[0])
        self.preference = (
            self.env["printnode.preference"]
            .with_user(self.people[0])
            .create(
                {
                    "paperformat_id": self.paper.id,
                    "printer_id": self.printers[0].id,
                }
            )
        )
        self.client = Mock()
        width, height = physical_size(self.paper)
        self.live_printer = {
            "id": self.printers[0].external_id,
            "name": "Receiving",
            "state": "online",
            "computer": {"name": "Desk", "state": "connected"},
            "capabilities": {"papers": {"fixture-paper": [height, width]}},
        }
        self.client.printer.return_value = self.live_printer
        self.client.submit.return_value = 73
        self.patch_client = patch.object(type(self.service), "_client", return_value=self.client)
        self.patch_client.start()
        self.addCleanup(self.patch_client.stop)
        self.saved_precommit = self.cr.precommit
        self.cr.precommit = type(self.saved_precommit)()
        self.addCleanup(setattr, self.cr, "precommit", self.saved_precommit)
        self.saved_callbacks = self.cr.postcommit
        self.cr.postcommit = type(self.saved_callbacks)()
        self.addCleanup(setattr, self.cr, "postcommit", self.saved_callbacks)

    def _prepare(self, **kwargs: object) -> dict:
        return self.service._prepare_print(b"%PDF-fixture", self.paper, content_type="pdf", title="Fixture label", **kwargs)

    def test_same_size_alias_and_other_company_keep_one_personal_route(self) -> None:
        self.assertEqual(self.service._resolve_printer(self.alias), self.printers[0])
        company = self.env["res.company"].create({"name": "Other fixture company"})
        self.people[0].sudo().company_ids = [Command.link(company.id)]
        switched = self.service.with_context(allowed_company_ids=[company.id])
        self.assertEqual(switched._resolve_printer(self.alias), self.printers[0])
        with self.assertRaises(UserError):
            self.service.with_user(self.people[1])._resolve_printer(self.paper)
        self.env["printnode.preference"].with_user(self.people[1]).create(
            {
                "paperformat_id": self.paper.id,
                "printer_id": self.printers[1].id,
            }
        )
        self.assertEqual(self.service.with_user(self.people[1])._resolve_printer(self.paper), self.printers[1])

    def test_preferences_are_isolated_including_forged_owner_and_sudo_writes(self) -> None:
        other = self.preference.with_user(self.people[1])
        self.assertFalse(other.search([("id", "=", self.preference.id)]))
        for operation in [
            lambda: other.read(["printer_id"]),
            lambda: other.write({"printer_id": self.printers[1].id}),
            other.unlink,
        ]:
            with self.assertRaises(AccessError):
                operation()
        for model in [other, other.sudo()]:
            with self.assertRaises(AccessError):
                model.create({"user_id": self.people[0].id, "paperformat_id": self.letter.id, "printer_id": self.printers[0].id})
            with self.assertRaises(AccessError):
                model.write({"user_id": self.people[1].id})
            with self.assertRaises(AccessError):
                model.with_context(default_user_id=self.people[0].id).create(
                    {"paperformat_id": self.letter.id, "printer_id": self.printers[0].id}
                )
        self.preference.with_user(self.admin).write({"printer_id": self.printers[1].id})

    def test_named_letter_and_size_picker_use_native_dimensions_without_aliases(self) -> None:
        choices = self.env["printnode.preference"]._paperformat_domain()[0][2]
        self.assertIn(self.paper.id, choices)
        self.assertNotIn(self.alias.id, choices)
        self.env["printnode.preference"].with_user(self.people[0]).create(
            {
                "paperformat_id": self.letter.id,
                "printer_id": self.printers[1].id,
            }
        )
        self.assertEqual(self.service._resolve_printer(self.letter), self.printers[1])
        bad = self.env["report.paperformat"].create({"name": "No size", "format": "custom"})
        with self.assertRaises(ValidationError):
            physical_size(bad)

    def test_missing_route_is_a_visible_error_and_never_a_silent_noop(self) -> None:
        with self.assertRaises(UserError) as error:
            self.service.with_user(self.people[1])._prepare_print(b"%PDF-fixture", self.paper, content_type="pdf", title="Missing")
        self.assertIn(str(self.paper.page_width), str(error.exception))
        self.client.submit.assert_not_called()
        self.client.printer.assert_not_called()
        self.assertNotIn(routing.BATCH_KEY, self.cr.postcommit.data)

    def test_printer_discovery_is_explicit_and_keeps_stale_choices(self) -> None:
        self.preference.read(["printer_id", "paperformat_id"])
        self.client.printers.assert_not_called()
        self.client.printers.return_value = [self.live_printer]
        self.env["printnode.printer"].with_user(self.people[0]).action_discover()
        self.assertIn(self.live_printer["computer"]["name"], self.preference.printer_id.name)
        self.client.printers.side_effect = transport.Unconfirmed()
        with self.assertRaises(UserError):
            self.env["printnode.printer"].with_user(self.people[0]).action_discover()
        self.assertEqual(self.preference.printer_id.external_id, self.live_printer["id"])

    def test_dimension_fields_cannot_forge_a_different_route(self) -> None:
        size = physical_size(self.paper)
        self.preference.write({"width": size[0] + 100, "height": size[1] + 100})
        self.assertEqual((self.preference.width, self.preference.height), size)
        self.assertEqual(self.service._resolve_printer(self.alias), self.printers[0])

    def test_stale_offline_and_wrong_paper_refuse_before_any_submission(self) -> None:
        for printer in [
            {**self.live_printer, "state": "offline"},
            {**self.live_printer, "computer": {"state": "disconnected"}},
            {**self.live_printer, "capabilities": None},
        ]:
            self.cr.postcommit.data.pop("printnode_direct_print.printers", None)
            self.client.printer.return_value = printer
            with self.assertRaises(UserError):
                self._prepare()
        self.client.printer.side_effect = transport.Rejected()
        self.cr.postcommit.data.pop("printnode_direct_print.printers", None)
        with self.assertRaises(UserError):
            self._prepare()
        self.client.submit.assert_not_called()
        self.assertNotIn(routing.BATCH_KEY, self.cr.postcommit.data)

    def test_closest_paper_is_bounded_and_exact_match_wins(self) -> None:
        width, height = physical_size(self.paper)
        tolerance = transport.PAPER_TOLERANCE_TENTHS_MM
        printer = {
            **self.live_printer,
            "capabilities": {
                "papers": {
                    "near": [width + tolerance, height],
                    "exact": [height, width],
                }
            },
        }
        self.assertEqual(self.service._matching_paper(printer, self.paper), "exact")
        del printer["capabilities"]["papers"]["exact"]
        self.assertEqual(self.service._matching_paper(printer, self.paper), "near")
        printer["capabilities"]["papers"]["near"][0] += 1
        with self.assertRaises(UserError):
            self.service._matching_paper(printer, self.paper)

    def test_raw_without_paper_capabilities_preserves_payload_and_own_quantities(self) -> None:
        self.client.printer.return_value = {**self.live_printer, "capabilities": None}
        payload = b"^XA^PQ7^XZ"
        result = self.service._prepare_print(payload, self.alias, content_type="raw", title="Raw")
        job = self.cr.postcommit.data[routing.BATCH_KEY][0]
        self.assertEqual(result["state"], "prepared")
        self.assertEqual(job.content, payload)
        self.assertEqual(job.quantity, 1)
        self.assertIsNone(job.paper)
        with self.assertRaises(UserError):
            self.service._prepare_print(payload, self.paper, content_type="raw", title="Raw", quantity=2)
        with self.assertRaises(UserError):
            self.service._prepare_print(b"%PDF-fixture", self.paper, content_type="raw", title="Wrong transport")

    def test_one_frozen_batch_waits_until_callback_and_cannot_claim_sent(self) -> None:
        result = self._prepare(quantity=2)
        self._prepare()
        self.assertEqual(result["state"], "prepared")
        self.assertNotIn("job_id", result)
        self.client.submit.assert_not_called()
        self.assertEqual(len(self.cr.postcommit), 1)
        self.client.printer.assert_called_once()
        jobs = self.cr.postcommit.data[routing.BATCH_KEY]
        self.preference.write({"printer_id": self.printers[1].id})
        self.assertEqual(jobs[0].printer_id, self.printers[0].external_id)
        self.assertEqual(jobs[0].quantity, 2)
        with (
            patch.object(routing, "notify_results") as notify,
            patch.object(routing, "take_committed_batch", return_value=(self.client, jobs)),
        ):
            self.cr.postcommit.run()
        self.assertEqual(self.client.submit.call_count, 2)
        self.assertEqual([entry[1] for entry in notify.call_args.args[2]], ["accepted", "accepted"])

    def test_failed_delivery_and_failed_notification_never_block_later_callbacks(self) -> None:
        self._prepare()
        self.client.submit.side_effect = transport.Unconfirmed()
        later = Mock()
        self.cr.postcommit.add(later)
        with (
            patch.object(routing, "notify_results", side_effect=RuntimeError("fixture notification failure")) as notify,
            patch.object(routing, "take_committed_batch", side_effect=lambda _registry, jobs: (self.client, jobs)),
        ):
            self.cr.postcommit.run()
        self.assertEqual(notify.call_args.args[2][0][1], "unconfirmed")
        later.assert_called_once()

    def test_nonhuman_and_portal_actors_refuse_even_with_sudo(self) -> None:
        for service in [
            self.service.with_user(1),
            self.service.with_context(cron_id=1),
            self.service.with_user(self.env.ref("base.public_user")),
        ]:
            with self.assertRaises(AccessError):
                service.sudo()._resolve_printer(self.paper)
        self.assertEqual(self.service.sudo()._resolve_printer(self.paper), self.printers[0])

    def test_report_and_python_route_share_actor_size_and_pdf_options(self) -> None:
        report = self.report.with_user(self.people[0])
        with patch.object(type(report), "_render_qweb_pdf", return_value=(b"%PDF-fixture", "pdf")) as render:
            result = report.printnode_print([self.people[0].partner_id.id])
        self.assertEqual(result["state"], "prepared")
        job = self.cr.postcommit.data[routing.BATCH_KEY][0]
        self.assertEqual(job.printer_id, self.service._resolve_printer(self.alias).external_id)
        self.assertEqual(job.content_type, "pdf")
        self.assertEqual(job.paper, "fixture-paper")
        self.assertEqual(render.call_args.kwargs["res_ids"], [self.people[0].partner_id.id])
        self.assertEqual(report.report_action([self.people[0].partner_id.id], config=False)["id"], report.id)

    def test_report_access_optin_data_and_company_are_checked_before_render(self) -> None:
        report = self.report.with_user(self.people[0])
        with patch.object(type(report), "_render_qweb_pdf") as render:
            with self.assertRaises(UserError):
                report.printnode_print([])
            self.report.printnode_direct = False
            with self.assertRaises(UserError):
                report.printnode_print([])
            self.report.printnode_direct = True
            self.report.group_ids = [Command.link(self.env.ref("base.group_system").id)]
            with self.assertRaises(AccessError):
                report.printnode_print([])
            self.report.group_ids = [Command.clear()]
            with self.assertRaises(UserError):
                report.printnode_print([], {"unapproved": True})
            with self.assertRaises(AccessError):
                report.with_context(allowed_company_ids=[self.env["res.company"].create({"name": "Forbidden"}).id]).printnode_print(
                    []
                )
            self.env["ir.access"].create(
                {
                    "name": "Fixture partner restriction",
                    "model_id": self.env["ir.model"]._get("res.partner").id,
                    "operation": "r",
                    "domain": "[('id', '=', user.partner_id.id)]",
                }
            )
            with self.assertRaises(AccessError):
                report.printnode_print([self.people[1].partner_id.id])
            render.assert_not_called()
        self.client.submit.assert_not_called()

    def test_validated_wizard_data_and_clean_action_metadata_survive(self) -> None:
        report = self.report.with_user(self.people[0]).with_context(active_model="wrong", active_ids=[99999], arbitrary="discard")
        data = {"form": {"quantity": 3}}
        with patch.object(type(report), "_printnode_validate_data", side_effect=lambda value: value):
            authorized, record_ids, preserved = report._authorized_print([self.people[0].partner_id.id], data)
        self.assertEqual(preserved, data)
        self.assertEqual(authorized.env.context["active_ids"], record_ids)
        self.assertEqual(authorized.env.context["active_model"], report.model)
        self.assertNotIn("arbitrary", authorized.env.context)

    def test_native_pdf_rendering_prepares_label_and_named_letter(self) -> None:
        view = self.env["ir.ui.view"].create(
            {
                "name": "Print fixture",
                "type": "qweb",
                "arch": '<html><head><meta charset="utf-8"/></head><body><main><div class="page"><t t-foreach="docs" t-as="doc"><span t-out="doc.name"/></t></div></main></body></html>',
            }
        )
        self.env["ir.model.data"].create(
            {
                "module": "printnode_direct_print",
                "name": "fixture_report_template",
                "model": "ir.ui.view",
                "res_id": view.id,
            }
        )
        self.report.report_name = "printnode_direct_print.fixture_report_template"
        self.env["printnode.preference"].with_user(self.people[0]).create(
            {
                "paperformat_id": self.letter.id,
                "printer_id": self.printers[0].id,
            }
        )
        self.client.printer.return_value = {
            **self.live_printer,
            "capabilities": {"papers": {"label": physical_size(self.paper), "letter": physical_size(self.letter)}},
        }
        with self.allow_pdf_render():
            for paper in (self.paper, self.letter):
                self.report.paperformat_id = paper
                size = physical_size(paper)
                result = (
                    self.report.with_user(self.people[0])
                    .with_context(force_report_rendering=True)
                    .printnode_print([self.people[0].partner_id.id])
                )
                self.assertEqual(result["state"], "prepared")
                job = self.cr.postcommit.data[routing.BATCH_KEY][-1]
                page = PdfReader(BytesIO(job.content)).pages[0]
                actual = sorted((float(page.mediabox.width) * 25.4 / 72, float(page.mediabox.height) * 25.4 / 72))
                for measured, expected in zip(actual, size, strict=True):
                    self.assertAlmostEqual(measured, expected / 10, delta=0.5)
        self.client.submit.assert_not_called()

    def test_native_notification_preserves_mixed_results_in_one_warning(self) -> None:
        self._prepare()
        job = self.cr.postcommit.data[routing.BATCH_KEY][0]
        results = [
            (job, "accepted", 73),
            (replace(job, title="Rejected fixture"), "unsent", None),
            (replace(job, title="Unknown fixture"), "unconfirmed", None),
        ]
        with patch.object(type(self.env["bus.bus"]), "_sendone") as send:
            routing.notify_results(self.registry, self.admin.id, results)
        message = send.call_args.args[2]
        self.assertEqual(message["type"], "warning")
        self.assertTrue(message["sticky"])
        for prepared, _status, _job_id in results:
            self.assertIn(prepared.title, message["message"])

    def test_native_commit_dispatches_and_rollback_discards_prior_attempt(self) -> None:
        with self.registry.cursor() as cursor:
            env = api.Environment(cursor, self.admin.id, {})
            paper = env["report.paperformat"].create(
                {"name": "Commit fixture", "format": "custom", "page_width": 57, "page_height": 31}
            )
            printer = env["printnode.printer"].sudo().create({"name": "Commit printer", "external_id": 12345})
            env["printnode.preference"].create({"paperformat_id": paper.id, "printer_id": printer.id})
            service = env["printnode.routing"]
            service._prepare_print(b"raw", paper, content_type="raw", title="Rolled back")
            cursor.rollback()
            self.assertFalse(cursor.postcommit.data)
            self.client.submit.assert_not_called()
            paper = env["report.paperformat"].create(
                {"name": "Commit fixture", "format": "custom", "page_width": 57, "page_height": 31}
            )
            printer = env["printnode.printer"].sudo().create({"name": "Commit printer", "external_id": 12345})
            env["printnode.preference"].create({"paperformat_id": paper.id, "printer_id": printer.id})
            service._prepare_print(b"raw", paper, content_type="raw", title="Committed")
            with patch.object(routing, "notify_results"):
                cursor.commit()
            self.client.submit.assert_called_once()
            self.assertEqual(self.client.submit.call_args.args[0].title, "Committed")
            env["printnode.preference"].search([("printer_id", "=", printer.id)]).unlink()
            printer.sudo().unlink()
            paper.unlink()
            cursor.commit()

    def test_savepoint_rollback_discards_only_its_prints_before_commit(self) -> None:
        with self.registry.cursor() as cursor:
            env = api.Environment(cursor, self.admin.id, {})
            paper = env["report.paperformat"].create(
                {"name": "Savepoint fixture", "format": "custom", "page_width": 57, "page_height": 31}
            )
            printer = env["printnode.printer"].sudo().create({"name": "Savepoint printer", "external_id": 12346})
            env["printnode.preference"].create({"paperformat_id": paper.id, "printer_id": printer.id})
            service = env["printnode.routing"]
            service._prepare_print(b"raw", paper, content_type="raw", title="Kept")
            for flush in (False, True):
                with self.assertRaises(ValueError):
                    with cursor.savepoint(flush=flush):
                        service._prepare_print(b"raw", paper, content_type="raw", title="Discarded")
                        raise ValueError("fixture rollback")
            with patch.object(routing, "notify_results"):
                cursor.commit()
            self.assertEqual([call.args[0].title for call in self.client.submit.call_args_list], ["Kept"])
            env["printnode.preference"].search([("printer_id", "=", printer.id)]).unlink()
            printer.sudo().unlink()
            paper.unlink()
            cursor.commit()

    def test_onchange_requests_cannot_prepare_a_print(self) -> None:
        with patch.object(routing, "request", Mock(params={"method": "onchange"})):
            with self.assertRaises(UserError):
                self._prepare()
        self.client.printer.assert_not_called()
        self.client.submit.assert_not_called()
