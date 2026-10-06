# Shared Addons

## Purpose

- Hold reusable cross-client addons consumed by tenant workspaces.

## Direction and Contributing

The Director's [overall DIRECTION.md](https://github.com/cbusillo/direction/blob/HEAD/DIRECTION.md)
sets priorities and stop boundaries; this repository has no separate direction
file. [AGENTS.md](AGENTS.md) routes repository work, review, and the Launchplane
merge-train handoff. Each addon's `AGENTS.md` holds its implementation guidance.

Workspace assembly and local runtime tooling belong to
[odoo-devkit](https://github.com/cbusillo/odoo-devkit). Tenant repositories own
assembled-environment validation and tenant-specific addons;
[Launchplane](https://github.com/cbusillo/launchplane) owns canonical runtime
configuration and release orchestration. Workflow facts and addon guide links
are in [`.github/github.json`](.github/github.json).

## Rules

- Shared addons must not depend on tenant-specific addons.
- Keep tenant-specific addons in tenant repos. Promote code here only when it
  is genuinely reusable across clients.

## Addon Inventory

- `authentik_sso`: Authentik OAuth2/OpenID Connect provider setup and group
  mapping helpers.
- `discuss_record_links`: Discuss/Chatter shortcuts for linking to business
  records.
- `environment_banner`: backend banner for identifying non-production
  environments.
- `external_ids`: generic external-system identity and URL-link management.
- `hr_employee_name_extended`: structured employee-name fields and formatting.
- `launchplane_settings`: adapter for applying Launchplane-managed instance
  settings inside Odoo.
- `notification_permission_patch`: browser notification permission observer for
  the Odoo web client.
- `test_support`: shared fixtures, test helpers, and base test cases.
- `transaction_utilities`: transaction and cron runtime-budget helpers.

## Addon CI

The Addon tests PR lane validates addon and test-input changes. See the
[shared addon-CI guide](https://github.com/cbusillo/odoo-devkit/blob/main/docs/tooling/addon-ci.md)
for the runner contract and local command.
