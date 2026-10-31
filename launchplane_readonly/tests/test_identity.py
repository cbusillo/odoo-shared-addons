import json
import os
from types import SimpleNamespace
from typing import Any
from unittest.mock import Mock, patch

from odoo import SUPERUSER_ID, Command
from odoo.exceptions import AccessDenied, AccessError
from odoo.http import request_var
from odoo.http.session import Session, SessionExpiredException, get_default_session, session_store
from odoo.service.model import call_kw
from odoo.tests import HttpCase, tagged
from odoo.tests.common import DEFAULT_SUCCESS_SIGNAL, JsonRpcException
from psycopg2.errors import ReadOnlySqlTransaction

from ..policy import COPY_PARAMETER, RUNTIME_ENV, product_login


@tagged("post_install", "-at_install")
class TestReadOnlyIdentity(HttpCase):
    def setUp(self) -> None:
        super().setUp()
        self.users = self.env["res.users"].with_user(SUPERUSER_ID)
        self.identity = {
            "schema_version": 1,
            "product": "synthetic-qa",
            "context": "synthetic",
            "instance": "testing",
            "environment_kind": "stable",
            "deployment_record_id": "deployment-a",
            "artifact_id": "artifact-a",
            "source_git_ref": "source-a",
        }
        self.runtime = patch.dict(os.environ, {RUNTIME_ENV: json.dumps(self.identity), "PLATFORM_INSTANCE": "testing"})
        self.runtime.start()
        self.addCleanup(self.runtime.stop)
        self.env["ir.config_parameter"].sudo().set_str(COPY_PARAMETER, "a" * 64)
        self.login = product_login(self.identity["product"])
        self.user = self.users._launchplane_readonly_test_identity(self.identity, self.login, create=True)

    def test_shell_is_credential_free_and_reused_without_activation(self) -> None:
        self.assertFalse(self.user.active)
        self.assertFalse(self.user.email)
        self.env.cr.execute("SELECT password FROM res_users WHERE id=%s", (self.user.id,))
        self.assertFalse(self.env.cr.fetchone()[0])
        self.assertEqual(self.user, self.users._launchplane_readonly_test_identity(self.identity, self.login, create=True))
        self.user.write({"active": True, "password": "synthetic-test-password"})
        self.assertEqual(self.user, self.users._launchplane_readonly_test_identity(self.identity, self.login))
        self.user.write({"active": False, "password": "synthetic-revocation-password"})
        self.assertEqual(self.user, self.users._launchplane_readonly_test_identity(self.identity, self.login))

    def test_staff_collision_and_privilege_drift_refuse(self) -> None:
        self.user.write({"launchplane_readonly_owner": False})
        with self.assertRaises(AccessError):
            self.users._launchplane_readonly_test_identity(self.identity, self.login, create=True)
        self.user.write({"launchplane_readonly_owner": self.users._launchplane_readonly_runtime_owner(self.identity)})
        self.user.write({"active": True, "password": "synthetic-password"})
        self.user.write({"group_ids": [Command.link(self.env.ref("base.group_erp_manager").id)]})
        with self.assertRaises(AccessError):
            self.users._launchplane_readonly_test_identity(self.identity, self.login)
        self.assertTrue(self.user.with_user(self.user)._launchplane_readonly_actor())
        self.user.write({"active": False, "password": "synthetic-revoked"})
        self.assertFalse(self.user.active)

    def test_production_and_stale_copy_refuse(self) -> None:
        for platform in ("", "prod", "production"):
            with patch.dict(os.environ, {"PLATFORM_INSTANCE": platform}), self.assertRaises(AccessError):
                self.users._launchplane_readonly_test_identity(self.identity, self.login)
        production = dict(self.identity, instance="prod")
        with (
            patch.dict(os.environ, {RUNTIME_ENV: json.dumps(production), "PLATFORM_INSTANCE": "prod"}),
            self.assertRaises(AccessError),
        ):
            self.users._launchplane_readonly_test_identity(production, self.login, create=True)
        self.env["ir.config_parameter"].sudo().set_str(COPY_PARAMETER, "b" * 64)
        with self.assertRaises(AccessError):
            self.users._launchplane_readonly_test_identity(self.identity, self.login)

    def test_preview_requires_fixture_and_retains_same_database_owner_after_refresh(self) -> None:
        self.identity.update(
            environment_kind="preview", instance="preview-example", preview_id="preview-a", preview_generation_id="one"
        )
        with patch.dict(os.environ, {RUNTIME_ENV: json.dumps(self.identity), "PLATFORM_INSTANCE": "preview"}):
            with self.assertRaises(AccessError):
                self.users._launchplane_readonly_fixture_identity(self.identity, create=True)
            self.user.unlink()
            self.assertFalse(self.users._launchplane_readonly_fixture_identity(self.identity))
            with self.assertRaises(AccessError):
                self.users._launchplane_readonly_test_identity(self.identity, self.login, create=True)
            preview_user = self.users._launchplane_readonly_fixture_identity(self.identity, create=True)
            preview_user.write({"password": "synthetic-password", "active": True})
            old = dict(self.identity)
            self.identity["preview_generation_id"] = "two"
            with patch.dict(os.environ, {RUNTIME_ENV: json.dumps(self.identity)}):
                with self.assertRaises(AccessError):
                    self.users._launchplane_readonly_test_identity(old, self.login)
                self.assertEqual(preview_user, self.users._launchplane_readonly_test_identity(self.identity, self.login))
                with self.assertRaises(AccessDenied):
                    preview_user.with_user(preview_user)._check_credentials(
                        {"type": "password", "password": "synthetic-password"}, {"interactive": True}
                    )
                settings = self.env["res.users.settings"]
                settings.search([("user_id", "=", preview_user.id)]).unlink()
                if "odoobot_state" in preview_user._fields:
                    preview_user.write({"odoobot_state": False})
                preview_user.write({"password": "synthetic-rotated"})
                preview_user._launchplane_readonly_check_session()
                self.assertTrue(settings.search([("user_id", "=", preview_user.id)]))
                preview_user.write({"active": False, "password": "synthetic-revoked"})

    def test_native_rpc_and_sudo_business_writes_refuse(self) -> None:
        partner = self.env["res.partner"].create({"name": "Synthetic business record"})
        readonly = partner.with_user(self.user)
        self.assertEqual(readonly.read(["name"])[0]["name"], partner.name)
        for operation in (
            lambda: call_kw(readonly, "write", [[partner.id], {"name": "changed"}], {}),
            lambda: readonly.sudo().write({"name": "changed"}),
            lambda: readonly.sudo().create({"name": "changed"}),
            lambda: readonly.sudo().unlink(),
            lambda: self.user.with_user(self.user).write({"tz": "Europe/Paris"}),
            lambda: self.user.with_user(self.user)._launchplane_readonly_test_identity(self.identity, self.login),
            lambda: self.env["ir.actions.server"].with_user(self.user).sudo().run(),
            lambda: self.env["ir.actions.report"].with_user(self.user).sudo().report_action([partner.id]),
            lambda: self.env["ir.actions.report"].with_user(self.user).sudo()._render_qweb_pdf("missing-report"),
            lambda: self.env["ir.actions.report"].with_user(self.user).sudo()._render_qweb_html("missing-report", [partner.id]),
            lambda: self.env["ir.actions.report"].with_user(self.user).sudo()._render_qweb_text("missing-report", [partner.id]),
        ):
            with self.subTest(operation=operation), self.assertRaises(AccessError):
                operation()
        self.assertEqual(partner.name, "Synthetic business record")
        ordinary = self.users.with_context(no_reset_password=True).create(
            {
                "name": "TEST Ordinary user",
                "login": "synthetic-ordinary",
                "group_ids": [Command.set(self.env.ref("base.group_user").ids)],
            }
        )
        partner.with_user(ordinary).sudo().write({"name": "Ordinary authorized write"})
        self.assertEqual(partner.name, "Ordinary authorized write")

    def test_legacy_credentials_and_api_keys_refuse_but_browser_password_works(self) -> None:
        self.user.write({"active": True, "password": "synthetic-password"})
        user = self.user.with_user(self.user)
        credential = {"type": "password", "password": "synthetic-password"}
        self.assertEqual(user._check_credentials(credential, {"interactive": True})["uid"], user.id)
        for auth_env in ({}, {"interactive": False}):
            with self.assertRaises(AccessDenied):
                user._check_credentials(credential, auth_env)
        with self.assertRaises(AccessDenied):
            user._check_credentials({"type": "apikey", "key": "synthetic"}, {"interactive": True})
        with self.assertRaises(AccessError):
            self.env["res.users.apikeys"].with_user(user).sudo().create({"name": "unsafe", "user_id": user.id})

    def test_readonly_dispatch_refuses_raw_sql_even_after_commit(self) -> None:
        fake = SimpleNamespace(env=self.env(user=self.user), session=SimpleNamespace(uid=self.user.id), params={})
        token = request_var.set(fake)
        self.addCleanup(request_var.reset, token)

        def write_sql() -> None:
            fake.env.cr.commit()
            fake.env.cr.execute("UPDATE res_partner SET name=name WHERE id=1")

        endpoint = Mock(side_effect=write_sql)
        endpoint.routing = {}
        original = self._registry_readonly_enabled
        try:
            for enabled in (True, False):
                self.set_registry_readonly_mode(enabled)
                before = endpoint.call_count
                with self.subTest(readonly_registry=enabled), self.assertRaises(AccessError) as refusal:
                    self.env.registry["ir.http"]._dispatch(endpoint)
                self.assertIsInstance(refusal.exception.__cause__, ReadOnlySqlTransaction)
                self.assertEqual(endpoint.call_count, before + 1)
        finally:
            self.set_registry_readonly_mode(original)
        self.assertIs(fake.env.cr, self.env.cr)

    def test_native_readonly_cursor_sees_uncommitted_records(self) -> None:
        partner = self.env["res.partner"].create({"name": "Synthetic uncommitted record"})
        self.env.flush_all()
        fake = SimpleNamespace(env=self.env(user=self.user), session=SimpleNamespace(uid=self.user.id), params={})
        token = request_var.set(fake)
        self.addCleanup(request_var.reset, token)

        def read_partner() -> str:
            return fake.env["res.partner"].browse(partner.id).name

        endpoint = Mock(side_effect=read_partner)
        endpoint.routing = {}
        self.assertEqual(self.env.registry["ir.http"]._dispatch(endpoint), partner.name)

    def test_native_login_keeps_only_authentication_bookkeeping(self) -> None:
        self.user.write({"active": True, "password": "synthetic-password"})
        logs = self.env["res.users.log"].sudo()
        before = logs.search_count([("create_uid", "=", self.user.id)])
        result = self.users._login(
            {"type": "password", "login": self.login, "password": "synthetic-password"}, {"interactive": True}
        )
        self.assertEqual(result["uid"], self.user.id)
        self.assertEqual(logs.search_count([("create_uid", "=", self.user.id)]), before + 1)

    def test_native_read_pre_dispatch_allows_superuser_configuration_reads(self) -> None:
        self.user.write({"active": True, "password": "synthetic-password"})
        dispatcher = SimpleNamespace(pre_dispatch=Mock())
        fake = SimpleNamespace(
            env=self.env(user=self.user),
            session=SimpleNamespace(uid=self.user.id),
            httprequest=SimpleNamespace(path="/web/session/get_session_info", max_content_length=None),
            dispatcher=dispatcher,
        )

        def update_context(**values: str) -> None:
            fake.env = fake.env(context=dict(fake.env.context, **values))

        fake.update_context = update_context
        token = request_var.set(fake)
        self.addCleanup(request_var.reset, token)
        function = SimpleNamespace(__name__="get_session_info", __self__=None)
        rule = SimpleNamespace(endpoint=SimpleNamespace(func=function, routing={"readonly": True}))
        self.env.registry["ir.http"]._pre_dispatch(rule, {})
        dispatcher.pre_dispatch.assert_called_once_with(rule, {})
        with self.assertRaises(AccessError):
            self.env["res.partner"].with_user(SUPERUSER_ID).create({"name": "Unsafe escalation"})

    def test_stale_session_logs_out_instead_of_trapping_the_browser(self) -> None:
        self.user.write({"active": True, "password": "synthetic-password"})
        session = Session(dict(get_default_session(), uid=self.user.id, db=self.env.cr.dbname), "synthetic-session")
        fake = SimpleNamespace(env=self.env(user=self.user), session=session, default_lang=lambda: "en_US")
        token = request_var.set(fake)
        self.addCleanup(request_var.reset, token)
        self.identity["deployment_record_id"] = "refreshed"
        with patch.dict(os.environ, {RUNTIME_ENV: json.dumps(self.identity)}), self.assertRaises(SessionExpiredException):
            self.env.registry["ir.http"]._pre_dispatch(None, {})
        self.assertFalse(session.uid)

    def test_request_guard_refuses_business_routes_before_dispatch(self) -> None:
        self.user.write({"active": True, "password": "synthetic-password"})
        self.user._launchplane_readonly_check_session()
        fake = SimpleNamespace(
            env=self.env(user=self.user), session=SimpleNamespace(uid=self.user.id), httprequest=SimpleNamespace(path="")
        )
        token = request_var.set(fake)
        self.addCleanup(request_var.reset, token)
        function = SimpleNamespace(__name__="business_write", __module__="synthetic", __self__=None)
        endpoint = SimpleNamespace(func=function, routing={"readonly": False})
        rule = SimpleNamespace(endpoint=endpoint)
        for path in ("/web/dataset/call_kw", "/mail/message/post", "/report/pdf/synthetic", "/web/action/run", "/web/export/csv"):
            fake.httprequest.path = path
            with self.subTest(path=path), self.assertRaises(AccessError):
                self.env.registry["ir.http"]._pre_dispatch(rule, {})

    def _login_browser(self) -> None:
        self.authenticate(None, None, session_extra={"_trace_disable": False})
        self.opener.cookies.set("tz", "Europe/Paris")
        result = self.make_jsonrpc_request(
            "/web/session/authenticate", {"db": self.env.cr.dbname, "login": self.login, "password": "synthetic-password"}
        )
        self.assertEqual(result["uid"], self.user.id)

    def test_real_webclient_starts_as_the_qa_identity(self) -> None:
        self.user.write({"active": True, "password": "synthetic-password"})
        self._login_browser()
        sid = self.opener.cookies.get_dict()["session_id"]
        self.addCleanup(session_store().delete, session_store().get(sid))
        self.session = None
        self.browser_js(
            "/odoo",
            f"""if (document.querySelector('.o_error_dialog')) throw new Error('QA bootstrap failed');
console.log({json.dumps(DEFAULT_SUCCESS_SIGNAL)});""",
            ready="Boolean(document.querySelector('.o_web_client .o_main_navbar'))",
            cookies={"session_id": sid},
        )

    def _rpc(self, model: str, method: str, args: list) -> Any:
        return self.make_jsonrpc_request("/web/dataset/call_kw", {"model": model, "method": method, "args": args, "kwargs": {}})

    def test_real_login_read_preferences_and_write_refusal(self) -> None:
        partner = self.env["res.partner"].create({"name": "Synthetic HTTP record"})
        self.user.write({"active": True, "password": "synthetic-password"})
        self._login_browser()
        self.assertEqual(self._rpc(partner._name, "read", [[partner.id], ["name"]])[0]["name"], partner.name)
        self.assertEqual(self._rpc(self.user._name, "action_get", [])["res_model"], self.user._name)
        with self.assertRaises(JsonRpcException):
            self._rpc(partner._name, "write", [[partner.id], {"name": "Unsafe HTTP write"}])
        with self.assertRaises(JsonRpcException):
            self._rpc(self.user._name, "write", [[self.user.id], {"tz": "UTC"}])
        partner.invalidate_recordset(["name"])
        self.assertEqual(partner.name, "Synthetic HTTP record")
        if "printnode.preference" in self.env.registry:
            preference = self.env["printnode.preference"]
            self.assertEqual(self._rpc(preference._name, "action_my_printers", [])["res_model"], preference._name)
            with patch.object(type(self.env["printnode.routing"]), "_client") as client:
                with self.assertRaises(JsonRpcException):
                    self._rpc("printnode.printer", "action_discover", [])
                client.assert_not_called()

    def test_service_prepares_cold_assets_before_qa_bootstrap(self) -> None:
        from lxml import html

        assets = self.env["ir.attachment"].sudo()
        domain = [("res_model", "=", "ir.ui.view"), ("res_id", "=", False), ("public", "=", True), ("url", "=like", "/web/assets/%")]
        assets.search(domain).unlink()
        self.user.write({"active": True, "password": "synthetic-password"})
        prepared_count = assets.search_count(domain)
        self.assertGreater(prepared_count, 0)
        self._login_browser()
        response = self.url_open("/odoo")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.url.endswith("/odoo"))
        document = html.fromstring(response.content)
        urls = [url for url in document.xpath("//script[@src]/@src | //link[@href]/@href") if url.startswith("/web/assets/")]
        self.assertTrue(urls)
        for url in urls:
            self.assertEqual(self.url_open(url).status_code, 200)
        self.assertEqual(assets.search_count(domain), prepared_count)
        if "odoobot_state" in self.user._fields:
            self.user.invalidate_recordset(["odoobot_state"])
            self.assertEqual(self.user.odoobot_state, "disabled")
