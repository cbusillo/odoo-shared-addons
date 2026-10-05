# HR Employee Name Extended

Structured first/last/nickname fields for `hr.employee` with locale-aware formatting and safe inverse writes.

## Features

- First/Last/Nickname fields with chatter tracking
- `name` stays Odoo's field (related to the employee's resource). Creating or writing the name parts sets `name`, and
  writing `name` alone (imports/API) is parsed back into structured parts
- Creating an employee from `name` alone, as Odoo does for a user's Create Employee action, splits the name into
  first and last name using the effective name format
- Locale-aware formatting: western (First Last) or asian (Last First)
- Per-employee format (`name_format`): System Default, western, or asian;
  Settings also supports a custom pattern
- Search across `name`, `first_name`, `last_name`, `nick_name`
- `display_name` shows `Nickname (First Last)` when nickname differs
- No cross-model side effects by default; partner/users sync remains opt-in via context (`allow_employee_sync`).
  Renaming a user without it leaves the employee's name unchanged

## Settings (HR)

- Default Name Format: western | asian | custom
- Custom Pattern (when format = custom): `{first_name}`, `{last_name}`, `{nickname}`

When `name_format` is omitted, new employees default it from Settings when the setting is western or asian,
including API and import creates.
An explicit per-employee format takes precedence on later name updates; System Default consults
the current Settings format, including a custom pattern. Changing Settings alone does not rename records.

## Admin Tools

- Server Action: "Recompute Employee Names" calls `hr.employee._action_recompute_names()` to recompose stored `name`
  in batches using each employee's format. Employees created while Settings was western or asian store that
  format explicitly. To apply changed defaults to those employees, select System Default on their records
  before recomputing. Changing Settings alone does not rename existing employees.
- Menu: HR → Configuration → Recompute Employee Names (no developer mode needed).

## Usage

- Set default format in HR Settings
- For employees who need a different order, set `Name Format` on the employee
- Writing `employee.name` as a single token keeps the last name unchanged

## Tests

- Unit tests cover: defaults, per-employee overrides, name parsing, settings impact, and bulk updates.
