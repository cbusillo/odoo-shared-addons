# AGENTS.md — external_ids

Purpose

- Safe helpers and views for inspecting/managing XML IDs (`ir.model.data`).

Key Points

- Read‑only surfaces by default; write operations gated by groups.
- Batch lookups via domain; copy/paste friendly.

Testing

- Unit: resolving IDs to records and back.
- Security: ensure non‑admins can’t unlink core data.

Implementation Notes

- Keep inspection surfaces read-only unless an operation is explicitly gated by
  the right Odoo group and covered by security tests.
- Debugging guidance should stay addon-specific here; workspace runtime tooling
  and assembled-environment workflows belong in `odoo-devkit` or tenant repos.
