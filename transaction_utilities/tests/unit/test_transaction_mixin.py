from contextlib import closing

from odoo import sql_db
from odoo.modules import module as odoo_module
from psycopg2.errors import InFailedSqlTransaction

from ..common_imports import common
from ..fixtures.base import UnitTestCase


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

    def _try_lock_from_other_session(self, lock_id: int) -> bool:
        # Advisory locks are re-entrant within one session, so only another
        # session can tell whether the lock is held.
        with closing(sql_db.db_connect(self.env.cr.dbname).cursor()) as other_cr:
            other_cr.execute("SELECT pg_try_advisory_lock(%s)", [lock_id])
            acquired = other_cr.fetchone()[0]
            if acquired:
                other_cr.execute("SELECT pg_advisory_unlock(%s)", [lock_id])
            return acquired

    def test_advisory_lock(self) -> None:
        with self.test_model._advisory_lock(12345) as acquired:
            self.assertTrue(acquired, "Should acquire advisory lock")
            self.assertFalse(self._try_lock_from_other_session(12345), "Lock should be held inside the block")

        self.assertTrue(self._try_lock_from_other_session(12345), "Lock should be released after the block")

    def test_advisory_lock_released_when_body_raises(self) -> None:
        lock_id = 12348
        try:
            with self.assertRaises(ValueError):
                with self.test_model._advisory_lock(lock_id) as acquired:
                    self.assertTrue(acquired)
                    self.assertFalse(self._try_lock_from_other_session(lock_id))
                    raise ValueError("Test body failed")
            self.assertTrue(self._try_lock_from_other_session(lock_id))
        finally:
            # A planted missing-unlock fault must not leak the lock into other tests.
            self.env.cr.execute("SELECT pg_advisory_unlock(%s)", [lock_id])

    def test_advisory_lock_not_acquired_when_held_elsewhere(self) -> None:
        with closing(sql_db.db_connect(self.env.cr.dbname).cursor()) as other_cr:
            other_cr.execute("SELECT pg_advisory_lock(%s)", [12347])
            with self.test_model._advisory_lock(12347) as acquired:
                self.assertFalse(acquired)
            other_cr.execute("SELECT pg_advisory_unlock(%s)", [12347])

    def test_advisory_lock_with_failed_transaction(self) -> None:
        original_execute = self.env.cr.execute
        unlock_call_count = 0

        def mock_execute(query: str, params: list | None = None) -> object:
            nonlocal unlock_call_count
            if "pg_try_advisory_lock" in query:
                return original_execute(query, params)
            if "pg_advisory_unlock" in query:
                unlock_call_count += 1
                raise InFailedSqlTransaction("current transaction is aborted")
            return original_execute(query, params)

        with common.patch.object(self.env.cr, "execute", side_effect=mock_execute):
            with self.test_model._advisory_lock(12346) as acquired:
                self.assertTrue(acquired, "Should acquire advisory lock")

            self.assertEqual(unlock_call_count, 1, "Should have attempted to unlock")

        self.env.cr.execute("SELECT pg_try_advisory_lock(%s)", [12346])
        lock_available = self.env.cr.fetchone()[0]
        if lock_available:
            self.env.cr.execute("SELECT pg_advisory_unlock(%s)", [12346])
