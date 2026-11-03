from collections.abc import Callable, Generator
from contextlib import ExitStack, closing, contextmanager
from typing import NamedTuple

from odoo import api, sql_db
from odoo.modules import module as odoo_module
from psycopg2.errors import DivisionByZero, InFailedSqlTransaction
from psycopg2.extensions import TRANSACTION_STATUS_IDLE
from psycopg2.extensions import connection as PsycopgConnection

from ..common_imports import common
from ..fixtures.base import UnitTestCase


class LockSessions(NamedTuple):
    caller: "odoo.model.transaction_mixin"
    observer: sql_db.Cursor
    borrow_cursor: Callable[[], sql_db.Cursor]


@common.tagged(*common.UNIT_TAGS)
class TestTransactionMixin(UnitTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.test_model = self.env["transaction.mixin"]

    def test_safe_commit_in_test_mode(self) -> None:
        with common.patch.object(self.test_model.env.cr, "commit") as mock_commit:
            self.test_model._safe_commit()
            mock_commit.assert_not_called()

    def test_safe_rollback_in_test_mode(self) -> None:
        with common.patch.object(self.test_model.env.cr, "rollback") as mock_rollback:
            self.test_model._safe_rollback()
            mock_rollback.assert_not_called()

    def test_safe_commit_outside_test_mode(self) -> None:
        from odoo.tools import config

        with common.patch.object(odoo_module, "current_test", False):
            with common.patch.object(config, "get", return_value=False):
                with common.patch.object(self.test_model.env.cr, "commit") as mock_commit:
                    self.test_model._safe_commit()
                    mock_commit.assert_called_once()

    def test_safe_rollback_outside_test_mode(self) -> None:
        from odoo.tools import config

        with common.patch.object(odoo_module, "current_test", False):
            with common.patch.object(config, "get", return_value=False):
                with common.patch.object(self.test_model.env.cr, "rollback") as mock_rollback:
                    self.test_model._safe_rollback()
                    mock_rollback.assert_called_once()

    def test_new_cursor_context_in_test_mode(self) -> None:
        with self.test_model._new_cursor_context() as new_env:
            self.assertIsNotNone(new_env)
            self.assertNotEqual(new_env.cr, self.test_model.env.cr)

            new_env["res.partner"].create({"name": "Test Partner in New Cursor", "email": "test_new_cursor@example.com"})

        partner = self.env["res.partner"].search([("email", "=", "test_new_cursor@example.com")])
        self.assertFalse(partner, "Partner should not exist in main cursor because no commit in test mode")

    @contextmanager
    def _lock_sessions(self) -> Generator[LockSessions]:
        dbname, connection_info = sql_db.connection_info_for(self.env.cr.dbname)
        database = sql_db.Connection(sql_db.ConnectionPool(maxconn=4), dbname, connection_info)
        borrow_cursor = database.cursor
        with ExitStack() as cleanup:

            def open_owned_cursor() -> sql_db.Cursor:
                cursor = borrow_cursor()
                cleanup.callback(cursor.close)
                cleanup.callback(cursor.connection.close)
                return cursor

            observer = open_owned_cursor()
            caller_cr = open_owned_cursor()
            caller = api.Environment(caller_cr, self.env.uid, self.env.context)["transaction.mixin"]
            with common.patch.object(sql_db, "db_connect", return_value=database):
                with common.patch.object(database, "cursor", side_effect=open_owned_cursor):
                    yield LockSessions(caller, observer, open_owned_cursor)

    @staticmethod
    def _try_lock(observer: sql_db.Cursor, lock_id: int) -> bool:
        observer.execute("SELECT pg_try_advisory_lock(%s)", [lock_id])
        acquired = observer.fetchone()[0]
        if acquired:
            observer.execute("SELECT pg_advisory_unlock(%s)", [lock_id])
        return acquired

    @staticmethod
    def _lock_owner(observer: sql_db.Cursor, lock_id: int) -> int:
        observer.execute(
            "SELECT pid FROM pg_locks WHERE locktype = 'advisory' AND classid = 0 AND objid = %s AND objsubid = 1 AND granted "
            "AND database = (SELECT oid FROM pg_database WHERE datname = current_database())",
            [lock_id],
        )
        return observer.fetchone()[0]

    def test_advisory_lock(self) -> None:
        lock_id = 12345
        with self._lock_sessions() as sessions:
            with sessions.caller._advisory_lock(lock_id) as acquired:
                self.assertTrue(acquired)
                self.assertFalse(self._try_lock(sessions.observer, lock_id))
            self.assertTrue(self._try_lock(sessions.observer, lock_id))

    def test_advisory_lock_released_when_body_raises(self) -> None:
        lock_id = 12348
        body_error = ValueError("Test body failed")
        with self._lock_sessions() as sessions:
            caller_cr = sessions.caller.env.cr
            caller_cr.execute("CREATE TEMP TABLE advisory_lock_sentinel (value integer) ON COMMIT DROP")
            caller_cr.execute("INSERT INTO advisory_lock_sentinel VALUES (1)")
            with self.assertRaises(ValueError) as raised:
                with sessions.caller._advisory_lock(lock_id) as acquired:
                    self.assertTrue(acquired)
                    self.assertFalse(self._try_lock(sessions.observer, lock_id))
                    raise body_error
            self.assertIs(raised.exception, body_error)
            caller_cr.execute("SELECT value FROM advisory_lock_sentinel")
            self.assertEqual(caller_cr.fetchone(), (1,))
            self.assertTrue(self._try_lock(sessions.observer, lock_id))

    def test_advisory_lock_not_acquired_when_held_elsewhere(self) -> None:
        lock_id = 12347
        with self._lock_sessions() as sessions:
            sessions.observer.execute("SELECT pg_advisory_lock(%s)", [lock_id])
            with sessions.caller._advisory_lock(lock_id) as acquired:
                self.assertFalse(acquired)

    def test_advisory_lock_releases_after_real_aborted_caller_and_pooled_return(self) -> None:
        lock_id = 12346
        with self._lock_sessions() as sessions:
            caller_cr = sessions.caller.env.cr
            caller_connection = caller_cr.connection
            with self.assertRaises(DivisionByZero):
                with sessions.caller._advisory_lock(lock_id) as acquired:
                    self.assertTrue(acquired)
                    self.assertFalse(self._try_lock(sessions.observer, lock_id))
                    owner_pid = self._lock_owner(sessions.observer, lock_id)
                    caller_cr.execute("SELECT 1 / 0", log_exceptions=False)
            with self.assertRaises(InFailedSqlTransaction):
                caller_cr.execute("SELECT 1", log_exceptions=False)
            with closing(sessions.borrow_cursor()) as returned:
                returned_pid = returned.connection.get_backend_pid()
                returned_status = returned.connection.get_transaction_status()
                lock_available = self._try_lock(sessions.observer, lock_id)
            self.assertTrue(lock_available, "Aborted body left its advisory lock held after pooled return")
            self.assertNotEqual(owner_pid, caller_connection.get_backend_pid())
            self.assertEqual(returned_pid, owner_pid)
            self.assertEqual(returned_status, TRANSACTION_STATUS_IDLE)
            caller_cr.rollback()
            caller_cr.execute("SELECT 1")
            self.assertEqual(caller_cr.fetchone(), (1,))

    def test_advisory_lock_preserves_caller_commits_rollbacks_and_pending_work(self) -> None:
        lock_id = 12349
        with self._lock_sessions() as sessions:
            caller_cr = sessions.caller.env.cr
            caller_cr.execute("CREATE TEMP TABLE advisory_lock_progress (value integer)")
            caller_cr.commit()
            with sessions.caller._advisory_lock(lock_id) as acquired:
                self.assertTrue(acquired)
                caller_cr.execute("INSERT INTO advisory_lock_progress VALUES (1)")
                caller_cr.commit()
                self.assertFalse(self._try_lock(sessions.observer, lock_id))
                caller_cr.execute("INSERT INTO advisory_lock_progress VALUES (2)")
                caller_cr.rollback()
                self.assertFalse(self._try_lock(sessions.observer, lock_id))
                caller_cr.execute("INSERT INTO advisory_lock_progress VALUES (3)")
            caller_cr.execute("SELECT value FROM advisory_lock_progress ORDER BY value")
            self.assertEqual(caller_cr.fetchall(), [(1,), (3,)])
            caller_cr.rollback()
            caller_cr.execute("SELECT value FROM advisory_lock_progress")
            self.assertEqual(caller_cr.fetchall(), [(1,)])
            self.assertTrue(self._try_lock(sessions.observer, lock_id))

    def test_advisory_lock_discards_failed_cleanup_without_masking_body_exception(self) -> None:
        for operation in ("execute", "disconnect", "close", "returned_close"):
            for body_fails in (False, True):
                with self.subTest(operation=operation, body_fails=body_fails):
                    self._check_cleanup_failure(operation, body_fails)

    def _check_cleanup_failure(self, operation: str, body_fails: bool) -> None:
        lock_id = 12350
        with self._lock_sessions() as sessions:
            method = "execute" if operation in ("execute", "disconnect") else "close"
            original = getattr(sql_db.Cursor, method)
            cleanup_error = RuntimeError("Test cleanup failed")
            body_error = ValueError("Test body failed")
            failed_connections: list[PsycopgConnection] = []
            next_borrowers: list[sql_db.Cursor] = []

            def fail_cleanup(cursor: sql_db.Cursor, *args: object, **kwargs: object) -> object:
                is_owned = cursor not in (sessions.observer, sessions.caller.env.cr)
                is_unlock = method == "execute" and "pg_advisory_unlock" in str(args[0]) and is_owned
                is_owned_close = method == "close" and is_owned
                if not failed_connections and (is_unlock or is_owned_close):
                    failed_connections.append(cursor.connection)
                    if operation == "disconnect":
                        cursor.connection.close()
                    if operation == "returned_close":
                        original(cursor, *args, **kwargs)
                        next_borrowers.append(sessions.borrow_cursor())
                    raise cleanup_error
                return original(cursor, *args, **kwargs)

            expected_error = body_error if body_fails else cleanup_error
            with self.assertLogs("odoo.addons.transaction_utilities.models.transaction_mixin", level="ERROR"):
                with common.patch.object(sql_db.Cursor, method, autospec=True, side_effect=fail_cleanup):
                    with self.assertRaises(type(expected_error)) as raised:
                        with sessions.caller._advisory_lock(lock_id) as acquired:
                            self.assertTrue(acquired)
                            self.assertFalse(self._try_lock(sessions.observer, lock_id))
                            if body_fails:
                                raise body_error
            self.assertIs(raised.exception, expected_error)
            if operation == "returned_close":
                next_borrower = next_borrowers[0]
                self.assertIs(next_borrower.connection, failed_connections[0])
                next_borrower.execute("SELECT 1")
                self.assertEqual(next_borrower.fetchone(), (1,))
            else:
                self.assertTrue(failed_connections[0].closed)
                with closing(sessions.borrow_cursor()) as first, closing(sessions.borrow_cursor()) as second:
                    self.assertIsNot(first.connection, failed_connections[0])
                    self.assertIsNot(second.connection, failed_connections[0])
            sessions.observer.execute("SET LOCAL lock_timeout = '5s'")
            sessions.observer.execute("SELECT pg_advisory_lock(%s)", [lock_id])
            sessions.observer.execute("SELECT pg_advisory_unlock(%s)", [lock_id])
