# AGENTS.md — Shared Addons Repo Guide

Treat this repo as the canonical home for reusable cross-client addon code.

## Scope

- Reusable shared addons only.
- Shared test support and shared infrastructure addons that still belong in the
  addon layer.

## Do Here

- Keep dependencies tenant-agnostic.
- Promote tenant logic here only when it is genuinely reusable across tenants.
- Keep addon-level docs and tests close to the addon they describe.

## Do Not Do Here

- Do not add tenant-specific wrappers, menus, or rollout notes.
- Do not treat this repo as the owner of runtime env/config authority.
- Do not reintroduce shared DX/runtime/bootstrap docs that belong in
  `odoo-devkit`.

## Related Repos

- `odoo-devkit` owns workspace assembly and local runtime tooling.
- `odoo-control-plane` owns canonical runtime env truth and release tuples.
- Tenant repos own tenant-specific addons and docs.
