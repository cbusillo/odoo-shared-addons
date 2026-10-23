# AGENTS.md — Shared Addons Repo Guide

Treat this repo as the canonical home for reusable cross-client addon code.

## Direction and Execution

Read the Director's [overall DIRECTION.md](https://github.com/cbusillo/direction/blob/HEAD/DIRECTION.md)
first. This repository has no separate `DIRECTION.md`; the overall direction
owns priorities, stop boundaries, and how pull requests land.

Use the maintained [executing loop](https://github.com/cbusillo/codex-skills/blob/main/skills/references/executing-loop.md)
for issue claims, isolated worktrees, implementation, and closeout, and
[reviews by another model](https://github.com/cbusillo/codex-skills/blob/main/skills/references/model-review.md)
to decide when a review is needed and how to weigh its findings.

`AGENTS.md` is the only agent-instruction filename. Addon guides inherit this
file and add only addon-specific guidance.

## Scope

- Reusable shared addons only.
- Shared test support and shared infrastructure addons that still belong in the
  addon layer.

## Do Here

- Keep dependencies tenant-agnostic.
- Promote tenant logic here only when it is genuinely reusable across tenants.
- Keep addon-level docs and tests close to the addon they describe.
- Write Python and Odoo JavaScript in the shared
  [Python and Odoo style](https://github.com/cbusillo/codex-skills/blob/HEAD/skills/references/python-odoo-style.md).

## Docs Routing

- This repo does not own a local `@docs` tree. Do not point addon guidance at
  `@docs/...` paths unless the owning workspace explicitly provides that alias.
- Keep reusable addon guidance in the addon guide itself, or name the owning
  repo/workspace when the authoritative docs live outside this repo.

## Tests

- Use [`.github/github.json`](.github/github.json) for validation gates and the
  [shared addon-CI guide](https://github.com/cbusillo/odoo-devkit/blob/main/docs/tooling/addon-ci.md)
  for the CI runner contract. Use `qualityGate.test.local` for focused local
  addon tests plus required lint and inspection; `ADDON_TEST_ROOT` must contain
  selected owned addon directories. The complete `qualityGate.test.ci` suite
  runs only in CI and must pass on the current head before `ready` or merge.
  Keep `addonOdoo` for validation by the pinned action; the action runs the
  runner with its workflow inputs. Checked `gh-pr.py ready` requires all
  current-head CI checks to pass before the enrolled train handoff.
- For safety, authorization, approval rules, destructive helpers and shared
  infrastructure, also run complete affected addon test modules locally.
  Auth/ACL/settings changes select the changed addon's full modules and all
  affected callers. Shared transaction/test-support changes select the full
  covering modules in every affected consumer addon. Follow the shared rule
  for required evidence that cannot run locally.
- Follow the shared [Tests rules](https://github.com/cbusillo/codex-skills/blob/main/instructions/global.md#tests).
- Odoo runs only the `test_*` modules that `tests/__init__.py` exposes. Wire a
  new test module through `expose_subdirectory_tests` or an explicit import, and
  confirm that the run log counts it.

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
