from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4

from odoo.exceptions import AccessError
from odoo.tests.common import TransactionCase, new_test_user
from odoo.tools import SQL
from psycopg2.errors import CheckViolation

from ..hooks import pre_init_hook


class TestDeviceHistory(TransactionCase):
    @property
    def logs(self) -> "odoo.model.res_device_log":
        return self.env["res.device.log"]

    @property
    def devices(self) -> "odoo.model.res_device":
        return self.env["res.device"]

    @property
    def sessions(self) -> "odoo.model.res_session":
        return self.env["res.session"]

    def _log(self, **values: object) -> "odoo.model.res_device_log":
        return self.logs.create(
            {
                "session_identifier": uuid4().hex,
                "user_id": self.env.uid,
                "ip_address": "192.0.2.1",
                "user_agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/130.0.0.0 Safari/537.36",
                "first_activity": datetime(2026, 1, 1),
                "last_activity": datetime(2026, 1, 1),
                **values,
            }
        )

    def _historical_log(self, **values: object) -> "odoo.model.res_device_log":
        return self._log(
            **{
                "user_agent": False,
                "legacy_user_agent_unavailable": True,
                "platform": "legacy platform",
                "browser": "legacy browser",
                "device_type": "mobile",
                **values,
            }
        )

    def test_historical_devices_and_session_keep_parsed_values(self) -> None:
        newest = self._historical_log(last_activity=datetime(2026, 1, 3))
        older = self._historical_log(
            session_identifier=newest.session_identifier,
            platform="older platform",
            browser="older browser",
            device_type="computer",
        )
        device = self.devices.browse(newest.id)
        session = self.sessions.browse(older.id)
        for record in (device, session):
            self.assertEqual(record.platform, newest.platform)
            self.assertEqual(record.browser, newest.browser)
            self.assertEqual(record.device_type, newest.device_type)
            self.assertFalse(record.user_agent)
            self.assertTrue(record.raw_user_agent_unavailable)
        self.assertIn(newest.browser.capitalize(), session.display_name)
        self.assertEqual(set(session.device_ids.ids), {newest.id, older.id})
        self.assertEqual(self.logs.browse([newest.id, older.id]).exists().ids, [newest.id, older.id])

    def test_native_telemetry_uses_parser_and_current_device(self) -> None:
        current = self._log()
        historical = self._historical_log(session_identifier=current.session_identifier, last_activity=datetime(2026, 1, 2))
        device = self.devices.browse(current.id)
        session = self.sessions.browse(historical.id)
        self.assertFalse(device.raw_user_agent_unavailable)
        self.assertFalse(current.legacy_user_agent_unavailable)
        self.assertNotEqual(device.browser, historical.browser)
        self.assertEqual(device.user_agent, current.user_agent)
        self.assertEqual(session.browser, historical.browser)
        self.env.invalidate_all()
        request = SimpleNamespace(
            session=SimpleNamespace(sid=current.session_identifier),
            httprequest=SimpleNamespace(remote_addr=current.ip_address, user_agent=SimpleNamespace(string=current.user_agent)),
        )
        with patch("odoo.addons.base.models.res_device.request", request):
            self.assertEqual(session.user_agent, current.user_agent)
            self.assertEqual(session.browser, device.browser)
            self.assertFalse(session.raw_user_agent_unavailable)

    def test_new_logs_without_raw_agent_are_rejected(self) -> None:
        with self.assertRaises(CheckViolation), self.env.cr.savepoint():
            self._log(user_agent=False)
        with self.assertRaises(CheckViolation), self.env.cr.savepoint():
            self.env.cr.execute(
                """
                INSERT INTO res_device_log
                    (session_identifier, user_id, ip_address, first_activity, last_activity)
                VALUES ('missing-agent', %s, '192.0.2.1', now(), now())
            """,
                [self.env.uid],
            )

    def test_empty_request_agent_is_not_historical(self) -> None:
        log = self._log(user_agent="")
        reference = self.devices.browse(self._log().id)
        device = self.devices.browse(log.id)
        session = self.sessions.browse(log.id)
        for record in (device, session):
            self.assertEqual(record.user_agent, log.user_agent)
            self.assertFalse(record.raw_user_agent_unavailable)
            self.assertEqual(record.device_type, reference.device_type)

    def test_native_cleanup_keeps_distinct_historical_logs(self) -> None:
        first = self._historical_log()
        second = self._historical_log(
            session_identifier=first.session_identifier, last_activity=first.last_activity + timedelta(days=1)
        )
        self.env["ir.config_parameter"].set_int("base.res_device_log_retention_days", 0)
        self.logs._gc_device_log()
        self.assertEqual(set((first | second).exists().ids), {first.id, second.id})

    def test_access_remains_limited_to_own_history(self) -> None:
        owner = new_test_user(self.env, login=f"history-{uuid4().hex}", groups="base.group_user")
        outsider = new_test_user(self.env, login=f"other-{uuid4().hex}", groups="base.group_user")
        administrator = new_test_user(self.env, login=f"admin-{uuid4().hex}", groups="base.group_system")
        portal = new_test_user(self.env, login=f"portal-{uuid4().hex}", groups="base.group_portal")
        log = self._historical_log(user_id=owner.id)
        for model in (self.devices, self.sessions, self.logs):
            record = model.browse(log.id)
            self.assertEqual(record.with_user(owner).platform, log.platform)
            self.assertEqual(record.with_user(administrator).platform, log.platform)
            for forbidden in (outsider, portal):
                with self.assertRaises(AccessError):
                    record.with_user(forbidden).read(["platform"])
        with self.assertRaises(AccessError):
            self.logs.with_user(owner).create({"user_agent": "forbidden"})

    def test_install_admits_only_existing_history(self) -> None:
        old = self._historical_log()
        native = self._log()
        self.env.cr.execute(
            SQL(
                "ALTER TABLE res_device_log DROP CONSTRAINT %s",
                SQL.identifier(self.logs._user_agent_present.full_name(self.logs)),
            )
        )
        self.env.cr.execute(
            """
            UPDATE res_device_log SET legacy_user_agent_unavailable = false WHERE id = %s
        """,
            [old.id],
        )
        pre_init_hook(self.env)
        (old | native).invalidate_recordset()
        self.assertTrue(old.legacy_user_agent_unavailable)
        self.assertFalse(native.legacy_user_agent_unavailable)
        self.assertFalse(old.user_agent)
        self.assertTrue(native.user_agent)

    def test_install_refuses_history_after_parsed_columns_are_lost(self) -> None:
        self._historical_log()
        self.env.cr.execute("ALTER TABLE res_device_log DROP COLUMN platform, DROP COLUMN browser, DROP COLUMN device_type")
        with self.assertRaises(RuntimeError):
            pre_init_hook(self.env)
