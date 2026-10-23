# Shared Addons

## Purpose

- Hold reusable cross-client addons consumed by tenant workspaces.

## Direction and Contributing

The Director's [overall DIRECTION.md](https://github.com/cbusillo/direction/blob/HEAD/DIRECTION.md)
sets priorities, stop boundaries, and how pull requests land; this repository
has no separate direction file. [AGENTS.md](AGENTS.md) routes repository work
and review. Each addon's `AGENTS.md` holds its implementation guidance.

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

The Addon tests lane runs the complete owned-addon suite on every PR head,
main push and train branch. See the
[shared addon-CI guide](https://github.com/cbusillo/odoo-devkit/blob/main/docs/tooling/addon-ci.md)
for the runner contract. The focused local and complete CI commands in
[`.github/github.json`](.github/github.json) reuse the `addonOdoo` declaration
through `jq`. The pinned action validates that declaration, then invokes the
runner with its workflow inputs; the CI command describes the full runner
step, rather than executing the action or its separate new-comment style check. For exact CI reproduction, use a
separate devkit checkout at the action revision in the workflow.

Export absolute `ODOO_DEVKIT_REPO`, `ADDON_TEST_OUTPUT` and `ADDON_TEST_ROOT`
paths. Export `ADDON_TEST_IMAGE` using the community image from the workflow.
Leave `ODOO_SHARED_ADDONS_REPO` unset, or export it as this task worktree's
`$PWD`, so dependencies come from the source under test.

Prepare a fresh selection immediately before each local run, for example:

```sh
mkdir -p "$(dirname "$ADDON_TEST_OUTPUT")"
export ADDON_TEST_ROOT="$(mktemp -d "$(dirname "$ADDON_TEST_OUTPUT")/focused-addons.XXXXXX")"
cp -R authentik_sso "$ADDON_TEST_ROOT/"
```

Copy each selected owned addon into that new directory; do not point the root
at one addon's directory, use host symlinks, or reuse stale copies after editing.
The support root supplies dependencies from the current worktree. CI selects
the full repository root. [Test rules](AGENTS.md#tests) own safety-module
selection and the checked readiness handoff; no branch setting changes here.

## TLS lint

Run the `qualityGate.lint.tls` command in `.github/github.json` before a PR.
The TLS lint workflow runs the five Ruff TLS rules plus the catalog's pinned
checker for hand-built verification disabling on PRs, main and train branches.
Update the checker pin through a source PR after reviewing its catalog change.

The shared SSL helper keeps verification enabled unless a site explicitly
disables it. Its single annotated exception records the approved private-path
Fishbowl compatibility decision; call sites need no duplicate comments. New
exceptions need a plain reason at their choke point and a permanent decision
link when applicable. A bare ignore is insufficient. These lint commands parse
source and do not connect to a tenant, alter settings or release an addon.
