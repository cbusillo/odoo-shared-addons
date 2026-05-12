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

## Docs Routing

- This repo does not own a local `@docs` tree. Do not point addon guidance at
  `@docs/...` paths unless the owning workspace explicitly provides that alias.
- Keep reusable addon guidance in the addon guide itself, or name the owning
  repo/workspace when the authoritative docs live outside this repo.
- Validation that depends on assembled tenants, browser tours, or runtime
  tooling should route through the relevant workspace or tenant repo.

## Do Not Do Here

- Do not add tenant-specific wrappers, menus, or rollout notes.
- Do not treat this repo as the owner of runtime env/config authority.
- Do not reintroduce shared DX/runtime/bootstrap docs that belong in
  `odoo-devkit`.

## Related Repos

- Keep non-secret workflow facts and validation routing in
  [`.github/github.json`](.github/github.json).
- `odoo-devkit` owns workspace assembly and local runtime tooling.
- `launchplane` owns canonical runtime env truth, release tuples, and
  promotion/deploy orchestration.
- Tenant repos own tenant-specific addons and docs.
