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

- [`website_consent_analytics`](website_consent_analytics/README.md) loads GA4 after native optional-cookie consent on selected websites.

- [`website_site_editor`](website_site_editor/README.md) lets assigned editors maintain prepared website pages, navigation and site settings.

- [`web_hierarchy_d3`](web_hierarchy_d3/README.md): opt-in interactive chart for Odoo hierarchy views.
- `authentik_sso`: Authentik OAuth2/OpenID Connect provider setup and group
  mapping helpers. Configuration methods are reserved for trusted callers.
  On an Authentik settings apply, `callback_mode` defaults to `provision` for
  internal-template signup and group mapping. Set it to `existing_user` to
  link a verified email to one active internal user's login or email. Returning
  users sign in by provider and subject. First linking trusts the provider to
  verify the current address and the Odoo account's login and email to identify
  its owner. These conditions must hold whenever a new identity links, including
  after an email change. Both paths preserve groups and reject
  invitation and reset tokens in this mode. An explicit `provision` or a new
  Authentik settings block omitting the selector restores the default. A payload
  without an Authentik block leaves the applied configuration in place. Unknown
  mode values fail validation. [Authentik email verification](https://docs.goauthentik.io/add-secure-apps/providers/oauth2/verify-email-address/)
  Other OAuth providers retain native signup, invitation, and portal-template
  behavior.

  To show only the configured Authentik button at the staff entry, set the
  database Boolean parameter `authentik_sso.staff_login_only` to true. Its
  default is false. The backend routes (`/odoo`, its deep links, `/web`, and
  scoped app links) pass their destination to the login page. The switch
  selects the form by that destination. Without the Website app, Odoo's
  anonymous site root also leads to the backend. Portal users can enter at
  `/my`. Direct `/web/login`, website and
  portal destinations, and invitation or reset links keep their existing
  sign-in methods. A provider error that returns to login without a backend
  destination also uses the ordinary form. Local administrators can sign in
  there with their existing credentials. The switch changes presentation only.

  Declare product defaults in the versioned product addon's XML data and list
  that file in its manifest. Odoo applies these native parameter setters on
  module install and update:

  ```xml
  <odoo>
      <function model="ir.config_parameter" name="set_bool" eval="('authentik_sso.staff_login_only', True)"/>
      <function model="ir.config_parameter" name="set_int" eval="('sessions.max_inactivity_seconds', 2592000)"/>
  </odoo>
  ```

  Products using the ordinary form can leave the Boolean unset. To turn it
  off after enabling it, set it to `False` on update. The two settings are
  independent. The integer sets about 30 days of inactivity database-wide,
  including portal accounts. Each browser profile keeps its own persistent
  cookie. Activity that refreshes the session renews the window, so an active
  session can last longer than 30 days. Scheduled cleanup removes stale
  session files by modification time. Where databases share one session
  directory, the shortest inactivity window can expire sessions for all of
  them. An absolute reauthentication interval at the identity provider is a
  separate provider policy.
- [`disable_odoo_online`](disable_odoo_online/README.md): skip the publisher-warranty
  phone-home call on self-hosted Odoo 20 Community.
- `discuss_record_links`: Discuss/Chatter shortcuts for linking to business
  records.
- [`device_history`](device_history/README.md): preserve historical parsed
  device information when raw User-Agent telemetry is unavailable.
- `environment_banner`: backend banner for identifying non-production
  environments.
- `external_ids`: generic external-system identity and URL-link management.
- `hr_employee_name_extended`: structured employee-name fields and formatting.
- [`house_standard`](house_standard/README.md): installs the house backend
  standard from the base image (MuK's Community backend theme and OCA's
  `document_page` wiki) and its
  defaults: contacts as cards, message panel below forms, an app-grid home and
  a lighter look.
- [`house_standard_hr`](house_standard/README.md#employee-hierarchy): styles the
  native employee hierarchy when Employees and House Standard are installed.
- [`launchplane_settings`](launchplane_settings/README.md): adapter for applying
  Launchplane-managed instance settings inside Odoo, with a pure installed
  payload projection for verified readers.
- [`launchplane_readonly`](launchplane_readonly/README.md): staff observer
  enforcement and owned read-only QA accounts. Tenant addons supply read access.
- `notification_permission_patch`: browser notification permission observer for
  the Odoo web client.
- [`printnode_direct_print`](printnode_direct_print/README.md): server-side
  personal printers by physical paper size, shared by report actions and save
  hooks, with submission after commit.
- [`product_numbering`](product_numbering/README.md): collision-aware product
  references and optional matching barcodes using OCA Product Sequence.
- `test_support`: shared fixtures, helpers and base cases; carrier-factory callers declare `delivery` themselves.
- `transaction_utilities`: transaction and cron runtime-budget helpers.

## Addon CI

This branch targets Community 20 and the qualified image pinned in the workflow.
Existing Odoo 19 consumers retain their exact source pins until their tenant
conversion advances both image and addons. Native `ir.access` policies preserve
the existing groups and operations; the employee-name addon has no owned access
policy. Parameter values use native string accessors so literal boolean strings
and integration credential clearing keep their existing meanings.

Odoo 20's native cross-module HOOT runner selects the owned JS suites for
desktop and mobile; addon-specific Python JS runner bridges are unnecessary.
Browser fixtures use the native disposable filestore, preserving isolation
without forcing database-only binary storage. Shared tours rely on Odoo to close
each tour's own Chromium process and remove its temporary profile.

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
selection.

## Shared style checks

The lint/format commands in [`.github/github.json`](.github/github.json) use
[Ruff and the inspection profile from devkit](https://github.com/cbusillo/odoo-devkit/blob/main/docs/tooling/style-checks.md).
`ruff.toml` inherits that configuration; the existing `ODOO_DEVKIT_REPO`
override selects a task checkout. The pinned addon-test action owns CI execution.
Use the native inspection helper's `--profile` option when the consumer checkout
is outside the normal sibling layout.

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
