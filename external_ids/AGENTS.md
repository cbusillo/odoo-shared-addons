# AGENTS.md — external_ids

Purpose

- Map Odoo records to their IDs in outside systems (`external.system`,
  `external.id`) and build links to those systems from URL templates
  (`external.system.url`).

Key Points

- Addons opt in by inheriting `external.id.mixin`. It adds the `external_ids`
  field, lookup and set helpers (`search_by_external_id`,
  `get_or_create_by_external_id`, `set_external_id`, `map_by_external_id`),
  the `record.external` reference API, and an External IDs tab on the form view
  unless the model sets `_external_ids_auto_ui = False`.
- An `ExternalIdBinding` on the model names its default system, so callers can
  use the `*_bound_external_id` helpers without passing a system code.
- Internal users can read; only `base.group_system` can create, edit, or delete,
  and the menu is limited to that group. `external.system.ensure_system()`
  creates and updates systems with `sudo()`, so call it only from install or
  admin code, never from a path a non-admin user can trigger.
- Active external IDs cannot be deleted (archive them first), and a system that
  still has IDs cannot be deleted.

Testing

- Unit: setting, finding, and mapping IDs through the mixin, URL building, and
  conflicts when two records claim the same ID in one system.
- Security: non-admin users can read but not change IDs or systems.

Implementation Notes

- Installations start with no seeded systems. Tenant addons create their own
  systems with `ensure_system()` and own their URL templates.
- Upgrade migration preserves historical system/link XML IDs with `noupdate`
  so existing external IDs and configured URLs survive removal of shared seeds.
- `external.id.fixture` is registered inside unit-test transactions only.
- Keep system-specific sync logic in the addon that talks to that system; this
  addon only stores identity and links.
- Debugging guidance should stay addon-specific here; workspace runtime tooling
  and assembled-environment workflows belong in `odoo-devkit` or tenant repos.
