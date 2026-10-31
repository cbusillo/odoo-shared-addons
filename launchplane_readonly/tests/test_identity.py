import json
import os
from types import SimpleNamespace
from unittest.mock import patch

from odoo import SUPERUSER_ID, Command, api
from odoo.exceptions import AccessDenied, AccessError
from odoo.http import request_var
from odoo.service.model import call_kw
from odoo.tests import TransactionCase, tagged
from psycopg2.errors import ReadOnlySqlTransaction

from ..policy import COPY_PARAMETER, GROUP, RUNTIME_ENV, product_login


@tagged("post_install", "-at_install")
class TestReadOnlyIdentity(TransactionCase):
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
        self.user.write({"group_ids": [Command.link(self.env.ref("base.group_erp_manager").id)]})
        with self.assertRaises(AccessError):
            self.users._launchplane_readonly_test_identity(self.identity, self.login)
        self.assertTrue(self.user.with_user(self.user)._launchplane_readonly_actor())

    def test_production_and_stale_copy_refuse_without_writes(self) -> None:
        for platform in ("", "prod", "production"):
            with patch.dict(os.environ, {"PLATFORM_INSTANCE": platform}), self.assertRaises(AccessError):
                self.users._launchplane_readonly_test_identity(self.identity, self.login)
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
            lambda: readonly.with_user(SUPERUSER_ID).write({"name": "changed"}),
            lambda: self.user.with_user(self.user).write({"tz": "Europe/Paris"}),
            lambda: call_kw(self.user.with_user(self.user), "_launchplane_readonly_test_identity", [self.identity, self.login], {}),
            lambda: self.env["ir.actions.server"].with_user(self.user).sudo().run(),
            lambda: self.env["ir.actions.report"].with_user(self.user).sudo().report_action([partner.id]),
            lambda: self.env["ir.actions.report"].with_user(self.user).sudo()._render_qweb_pdf("missing-report"),
        ):
            with self.subTest(operation=operation), self.assertRaises(AccessError):
                operation()
        self.assertEqual(partner.name, "Synthetic business record")
        partner.write({"name": "Ordinary authorized write"})
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

        write_sql.routing = {}
        with self.assertRaises(ReadOnlySqlTransaction):
            self.env.registry["ir.http"]._dispatch(write_sql)
        self.assertIs(fake.env.cr, self.env.cr)

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
