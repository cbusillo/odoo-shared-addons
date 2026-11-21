import json
from unittest.mock import patch

from lxml import html
from odoo import Command
from odoo.exceptions import AccessError
from odoo.tests import HttpCase, tagged
from odoo.tests.common import JsonRpcException

from .http_cursor import initial_writable_rpc_cursor


@tagged("post_install", "-at_install")
class TestStaffObserver(HttpCase):
    def setUp(self) -> None:
        super().setUp()
        if "sale.order" not in self.env or "stock.reference" not in self.env:
            self.skipTest("Requires Sales and Stock for native work-role and ambient-write controls.")
        self.observer_group = self.env.ref("launchplane_readonly.group_staff_observer")
        self.sales_group = self.env.ref("sales_team.group_sale_salesman")
        self.sales_only = self._user("sales", self.sales_group)
        self.observer = self._user("observer", self.observer_group)
        self.combined = self._user("combined", self.observer_group | self.sales_group)
        self.env["ir.access"].create(
            {
                "name": "Synthetic observer quotation read",
                "model_id": self.env["ir.model"]._get("sale.order").id,
                "group_id": self.observer_group.id,
                "operation": "r",
            }
        )
        customer = self.env["res.partner"].create({"name": "Synthetic quotation customer"})
        self.outside = self.env["sale.order"].create({"partner_id": customer.id, "user_id": self.env.uid})
        self.sales_quote = self.env["sale.order"].create({"partner_id": customer.id, "user_id": self.sales_only.id})
        self.combined_quote = self.env["sale.order"].create({"partner_id": customer.id, "user_id": self.combined.id})
        self.reference = self.env["stock.reference"].create({"name": "Synthetic staff reference"})
        work_role = patch.object(
            type(self.observer),
            "_staff_observer_work_groups",
            return_value=("sales_team.group_sale_salesman",),
        )
        work_role.start()
        self.addCleanup(work_role.stop)

    def _user(self, role: str, groups: "odoo.model.res_groups") -> "odoo.model.res_users":
        login = f"synthetic-staff-{role}"
        return self.env["res.users"].create(
            {
                "name": login,
                "login": login,
                "password": login,
                "group_ids": [Command.set(groups.ids)],
            }
        )

    def _staff_login(self, user: "odoo.model.res_users") -> None:
        self.env.flush_all()
        self.authenticate(None, None)
        result = self.make_jsonrpc_request(
            "/web/session/authenticate", {"db": self.env.cr.dbname, "login": user.login, "password": user.login}
        )
        self.assertEqual(result["uid"], user.id)

    def _rpc(self, model: str, method: str, args: list) -> list | dict | bool:
        return self.make_jsonrpc_request("/web/dataset/call_kw", {"model": model, "method": method, "args": args, "kwargs": {}})

    def test_observer_can_sign_in_and_read_without_saving_writes(self) -> None:
        self._staff_login(self.observer)
        response = self.url_open("/odoo")
        self.assertTrue(response.url.endswith("/odoo"))
        self.assertEqual(self._rpc("sale.order", "read", [[self.outside.id], ["name"]])[0]["name"], self.outside.name)

        with self.assertRaises(JsonRpcException):
            self._rpc("stock.reference", "write", [[self.reference.id], {"name": "Unexpected observer write"}])
        with self.assertRaises(AccessError), self.env.cr.savepoint():
            self.reference.with_user(self.observer).create({"name": "Unexpected observer creation"})
        with self.assertRaises(AccessError), self.env.cr.savepoint():
            self.reference.with_user(self.observer).sudo().unlink()
        with self.assertRaises(AccessError), self.env.cr.savepoint():
            self.outside.with_user(self.observer).action_preview_sale_order()

        self.env.invalidate_all()
        self.assertEqual(self.reference.name, "Synthetic staff reference")
        self.assertFalse(self.outside.access_token)
        self.assertFalse(self.reference.search_count([("name", "=", "Unexpected observer creation")]))

    def test_native_oauth_signin_preserves_observer_policy(self) -> None:
        if "auth.oauth.provider" not in self.env:
            self.skipTest("Requires the OAuth addon used by the tenant.")
        provider = self.env["auth.oauth.provider"].create(
            {
                "name": "Synthetic OAuth provider",
                "client_id": "synthetic-staff-client",
                "auth_endpoint": "https://staff.example.test/authorize",
                "body": "Sign in with synthetic OAuth",
                "validation_endpoint": "https://staff.example.test/userinfo",
            }
        )
        subject = "synthetic-staff-subject"
        self.observer.write({"oauth_provider_id": provider.id, "oauth_uid": subject})
        self.env.flush_all()
        self.authenticate(None, None)
        state = json.dumps({"d": self.env.cr.dbname, "p": provider.id})
        with patch.object(type(self.observer), "_auth_oauth_rpc", return_value={"sub": subject}):
            response = self.url_open("/auth_oauth/signin", params={"state": state, "access_token": "synthetic-staff-token"})
        self.assertTrue(response.url.endswith("/odoo"))
        session = self.make_jsonrpc_request("/web/session/get_session_info", {})
        self.assertEqual(session["uid"], self.observer.id)
        self.assertEqual(self._rpc("sale.order", "read", [[self.outside.id], ["name"]])[0]["name"], self.outside.name)
        with self.assertRaises(JsonRpcException):
            self._rpc("sale.order", "action_preview_sale_order", [[self.outside.id]])
        self.outside.invalidate_recordset(["access_token"])
        self.assertFalse(self.outside.access_token)

    def test_observer_reads_cannot_expand_sales_role_writes(self) -> None:
        for user, quotation in ((self.sales_only, self.sales_quote), (self.combined, self.combined_quote)):
            with self.subTest(user=user.login):
                self._staff_login(user)
                if user == self.combined:
                    self.assertEqual(self._rpc("sale.order", "read", [[self.outside.id], ["name"]])[0]["name"], self.outside.name)
                else:
                    with self.assertRaises(JsonRpcException):
                        self._rpc("sale.order", "read", [[self.outside.id], ["name"]])
                with self.assertRaises(JsonRpcException):
                    self._rpc("sale.order", "write", [[self.outside.id], {"note": "Unexpected outside write"}])
                with self.assertRaises(JsonRpcException):
                    self._rpc("sale.order", "action_preview_sale_order", [[self.outside.id]])
                self.assertTrue(self._rpc("sale.order", "write", [[quotation.id], {"note": "Saved by Sales"}]))
                self._rpc("sale.order", "action_preview_sale_order", [[quotation.id]])

                self.env.invalidate_all()
                self.assertIn("Saved by Sales", quotation.note)
                self.assertTrue(quotation.access_token)
                self.assertFalse(self.outside.access_token)
                self.assertNotIn("Unexpected outside write", self.outside.note or "")

    def test_combined_staff_keeps_work_scope_on_a_writable_initial_cursor(self) -> None:
        self._staff_login(self.combined)
        with initial_writable_rpc_cursor(self):
            self.assertEqual(self._rpc("sale.order", "read", [[self.outside.id], ["name"]])[0]["name"], self.outside.name)
        with initial_writable_rpc_cursor(self), self.assertRaises(JsonRpcException):
            self._rpc("sale.order", "action_preview_sale_order", [[self.outside.id]])
        with initial_writable_rpc_cursor(self):
            self._rpc("sale.order", "action_preview_sale_order", [[self.combined_quote.id]])
        self.env.invalidate_all()
        self.assertTrue(self.combined_quote.access_token)
        self.assertFalse(self.outside.access_token)

    def test_observer_can_refresh_with_cold_generated_assets(self) -> None:
        self._staff_login(self.observer)
        assets = self.env["ir.attachment"].search(
            [
                ("url", "=like", "/web/assets/%"),
                ("res_model", "=", "ir.ui.view"),
            ]
        )
        self.assertTrue(assets)
        assets.unlink()
        self.env.flush_all()

        response = self.url_open("/odoo")
        self.assertTrue(response.url.endswith("/odoo"))
        urls = [
            url
            for url in html.fromstring(response.content).xpath("//script[@src]/@src | //link[@href]/@href")
            if url.startswith("/web/assets/")
        ]
        self.assertTrue(urls)
        for url in urls:
            self.assertEqual(self.url_open(url).status_code, 200, url)
