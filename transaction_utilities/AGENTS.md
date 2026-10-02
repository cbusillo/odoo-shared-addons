# AGENTS.md — transaction_utilities

## Scope

- Transaction safety helpers only: `transaction.mixin` (commit/rollback, a new
  cursor, advisory locks) and `transaction.cron_budget.mixin` (stop a long cron
  run cleanly before its runtime limit).
- No business logic or client-specific behavior.

## Notes

- Keep dependencies minimal (base only).
