# HR Employee Name Extended

Structured first/last/nickname fields for `hr.employee` with locale-aware formatting and safe inverse writes.

## Features

- First/Last/Nickname fields with chatter tracking
- `name` stays Odoo's field (related to the employee's resource). Creating or writing the name parts sets `name`, and
  writing `name` alone (imports/API) is parsed back into structured parts
- Locale-aware formatting: western (First Last) or asian (Last First)
- Per-employee override (`name_format`) with optional default from Settings
- Search across `name`, `first_name`, `last_name`, `nick_name`
- `display_name` shows `Nickname (First Last)` when nickname differs
- No cross-model side effects by default; partner/users sync remains opt-in via context (`allow_employee_sync`).
  Renaming a user without it leaves the employee's name unchanged

## Settings (HR)

- Default Name Format: western | asian | custom
- Custom Pattern (when format = custom): `{first_name}`, `{last_name}`, `{nickname}`

Defaults apply only when creating a new employee; name updates always respect the per-employee override.

## Admin Tools

- Server Action: "Recompute Employee Names" calls `hr.employee._action_recompute_names()` to recompute stored `name` in
  batches after changing settings. Changing the format does not rename existing employees until this runs.
- Menu: HR → Configuration → Recompute Employee Names (no developer mode needed).

## Usage

- Set default format in HR Settings
- For employees who need a different order, set `Name Format` on the employee
- Writing `employee.name` as a single token keeps the last name unchanged

## Tests

- Unit tests cover: defaults, per-employee overrides, name parsing, settings impact, and bulk updates.
