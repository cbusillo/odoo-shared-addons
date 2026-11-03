# AGENTS.md — transaction_utilities

## Scope

- Transaction safety helpers only: `transaction.mixin` (commit/rollback, a new
  cursor, advisory locks) and `transaction.cron_budget.mixin` (stop a long cron
  run cleanly before its runtime limit).
- No business logic or client-specific behavior.

## Notes

- Keep dependencies minimal (base only).
- `_advisory_lock` owns one additional pooled session while its context is open.
  It ends only its acquisition transaction and explicitly unlocks before normal
  pooled return. Cleanup failure discards only that session; a body exception
  takes precedence, while cleanup failure after a healthy body propagates.
- The caller owns its transaction, including commits, rollbacks and recovery
  after SQL errors. Same-key nested helper calls contend because each context
  uses a separate session.
