# AGENTS.md — hr_employee_name_extended

Purpose

- Structured first/last/nickname fields on `hr.employee` with locale-aware
  formatting and safe inverse writes.

Key Models/Fields

- `hr.employee` adds: `first_name`, `last_name`, `nick_name`, and
  `name_format` (selection: System Default (empty), `western`, or `asian`).
- `name`: Odoo 19 keeps it related to `resource_id.name`, which ignores
  compute/inverse overrides. `create()` and `write()` compose it from the parts,
  and a write of `name` alone parses back to parts.

Settings

- `res.config.settings`: `user_name_format` (default format) and
  `user_name_custom_pattern` (when custom).

Admin Tools

- Server Action `action_recompute_employee_names` calls
  `env['hr.employee']._action_recompute_names()`.
- Menu: HR > Configuration > Recompute Employee Names.

Usage Notes

- Changing defaults does not retro-update records. The server action recomputes
  in batches, preserving explicit per-employee formats; changed defaults affect
  employees using System Default.
- Writing `employee.name` with a single token keeps the last name unchanged.

Tests

- See `tests/` for settings, inverse, per-employee overrides, and bulk recompute
  cases.

Implementation Notes

- Keep shared name formatting tenant-neutral and avoid locale assumptions that
  belong in tenant-specific configuration.
- Cover compute, inverse, per-record override, recompute, and access-rule cases
  when changing name composition behavior.
