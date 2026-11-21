import json
from contextlib import nullcontext
from typing import Any
from unittest.mock import patch

from lxml import html
from odoo import Command
from odoo.exceptions import AccessError
from odoo.tests import HttpCase, tagged
from odoo.tests.common import JsonRpcException

from .http_cursor import initial_writable_cursor


@tagged("post_install", "-at_install")
class TestStaffObserver(HttpCase):
    def setUp(self) -> None:
        super().setUp()
        sales = self._fixture_model("sale.order")
        stock_references = self._fixture_model("stock.reference")
        self.observer_group = self.env.ref("launchplane_readonly.group_staff_observer")
        sales_group_xmlid = "sales_team.group_sale_salesman"
        self.sales_group = self.env.ref(sales_group_xmlid)
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
        self.outside = sales.create({"partner_id": customer.id, "user_id": self.env.uid})
        self.sales_quote = sales.create({"partner_id": customer.id, "user_id": self.sales_only.id})
        self.combined_quote = sales.create({"partner_id": customer.id, "user_id": self.combined.id})
        self.reference = stock_references.create({"name": "Synthetic staff reference"})
        work_role = patch.object(
            type(self.observer),
            "_staff_observer_work_groups",
            return_value=(sales_group_xmlid,),
        )
        work_role.start()
        self.addCleanup(work_role.stop)

    def _fixture_model(self, model: str) -> Any:
        if model not in self.env:
            self.skipTest(f"The native fixture requires {model}.")
        return self.env[model]

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

    def _rpc(self, model: str, method: str, args: list) -> Any:
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
        provider = self._fixture_model("auth.oauth.provider").create(
            {
                "name": "Synthetic OAuth provider",
                "client_id": "synthetic-staff-client",
                "auth_endpoint": "https://staff.example.test/authorize",
                "body": "Sign in with synthetic OAuth",
                "validation_endpoint": "https://staff.example.test/userinfo",
            }
        )
        subject = "synthetic-staff-subject"
        oauth_user = self._fixture_model("res.users").browse(self.observer.id)
        oauth_user.write({"oauth_provider_id": provider.id, "oauth_uid": subject})
        self.env.flush_all()
        self.authenticate(None, None)
        state = json.dumps({"d": self.env.cr.dbname, "p": provider.id})
        with patch.object(type(oauth_user), "_auth_oauth_rpc", return_value={"sub": subject}):
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
        with initial_writable_cursor(self):
            self.assertEqual(self._rpc("sale.order", "read", [[self.outside.id], ["name"]])[0]["name"], self.outside.name)
        with initial_writable_cursor(self), self.assertRaises(JsonRpcException):
            self._rpc("sale.order", "action_preview_sale_order", [[self.outside.id]])
        with initial_writable_cursor(self):
            self._rpc("sale.order", "action_preview_sale_order", [[self.combined_quote.id]])
        self.env.invalidate_all()
        self.assertTrue(self.combined_quote.access_token)
        self.assertFalse(self.outside.access_token)

    def test_signed_in_observer_can_refresh_and_reuse_changed_assets(self) -> None:
        self._staff_login(self.observer)
        session_id = self.opener.cookies["session_id"]
        for native_readonly in (True, False):
            with self.subTest(native_readonly=native_readonly):
                self._refresh_observer_assets(native_readonly=native_readonly)
                self.assertEqual(self.opener.cookies["session_id"], session_id)

    def _observer_asset_urls(self) -> dict[str, str]:
        response = self.url_open("/odoo")
        self.assertTrue(response.url.endswith("/odoo"))
        document = html.fromstring(response.content)
        paths = document.xpath("//script[@src]/@src | //link[@href]/@href")
        web = {kind: next(path for path in paths if path.endswith(f"/web.assets_web.min.{kind}")) for kind in ("js", "css")}
        worker = self.env["ir.qweb"]._get_asset_bundle("bus.websocket_worker_assets", css=False)
        return web | {"worker": worker.get_link("js")}

    def _generated_assets(self, urls: dict[str, str]) -> "odoo.model.ir_attachment":
        return self.env["ir.attachment"].search(
            [("url", "in", list(urls.values())), ("res_model", "=", "ir.ui.view"), ("res_id", "=", 0), ("public", "=", True)]
        )

    def _change_asset_bundles(self, version: str) -> None:
        for kind, content in (
            ("js", f'globalThis.staffObserverAssetVersion = "{version}";'),
            ("css", f".staff-observer-refresh {{ --staff-observer-version: {version}; }}"),
        ):
            path = f"/staff-observer-{version}.{kind}"
            self.env["ir.attachment"].create({"name": path, "url": path, "raw": content.encode(), "public": True})
            bundles = ("web.assets_web", "bus.websocket_worker_assets") if kind == "js" else ("web.assets_web",)
            self.env["ir.asset"].create([{"name": path, "path": path, "bundle": bundle} for bundle in bundles])
        self.env.flush_all()

    def _fetch_observer_asset(self, path: str, *, native_readonly: bool) -> bytes:
        cursor = nullcontext()
        if not native_readonly and path.startswith("/web/assets/"):
            cursor = initial_writable_cursor(self, path)
        with cursor:
            response = self.url_open(path, allow_redirects=False)
        self.assertEqual(response.status_code, 200, path)
        return response.content

    def _refresh_observer_assets(self, *, native_readonly: bool) -> None:
        previous = self._observer_asset_urls()
        self.assertEqual(set(self._generated_assets(previous).mapped("url")), set(previous.values()))

        version = "staff-observer-readonly" if native_readonly else "staff-observer-writable"
        self._change_asset_bundles(version)
        current = self._observer_asset_urls()
        for kind, url in current.items():
            self.assertNotEqual(url, previous[kind])
        self.assertFalse(self._generated_assets(current))

        paths = current | {"worker": "/bus/websocket_worker_bundle"}
        contents = {}
        for kind, path in paths.items():
            content = self._fetch_observer_asset(path, native_readonly=native_readonly)
            self.assertIn(version.encode(), content)
            contents[current[kind]] = content

        saved = self._generated_assets(current)
        self.assertEqual(set(saved.mapped("url")), set(contents))
        for record in saved:
            self.assertTrue(record.raw.content == contents[record.url], record.url)
        for kind, path in paths.items():
            content = self._fetch_observer_asset(path, native_readonly=native_readonly)
            self.assertTrue(content == contents[current[kind]], path)
        self.assertEqual(self._generated_assets(current), saved)
