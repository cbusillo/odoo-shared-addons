# Read-only QA identities

This addon supplies `launchplane_readonly.group_user`, private account
qualification and server-side read-only enforcement for Odoo 20. It installs
no account, credential, business permissions or menus. Tenant addons add native
`ir.access` read permissions and menu access directly on this role. The role
implies only Internal User, whose existing read access remains available.

Launchplane's fixed native consumer calls
`res.users._launchplane_readonly_test_identity(identity, login, create=False)`.
Testing may use `create=True`. Preview consumers qualify an existing shell;
only the tenant's credential-free fixture calls
`res.users._launchplane_readonly_fixture_identity(identity, create=False)`.
The fixture helper derives the login, returns an empty recordset for an absent,
collision-free shell, and creates an inactive shell when `create=True`.
Both helpers use only the caller's transaction and never commit or set a password.
The pure `policy.product_login(product)` implements the LP login contract once.

Qualification compares the caller to `LAUNCHPLANE_RUNTIME_IDENTITY_JSON`,
requires the appropriate `PLATFORM_INSTANCE` (`testing` or `preview`), and
binds ownership to the product, context, instance, database name and UUID.
Testing additionally binds the native completed-copy witness. Preview ownership
includes its preview ID; each caller must name the current native generation.
A historical witness on the same preview/database survives a refresh for
cleanup, but a testing witness never establishes preview ownership. A collision
with an active or archived staff login is refused. Extra roles, changed
implications, API keys, missing ownership and unknown/production targets refuse.

The native service superuser owns activation/password changes. Such a write
also binds authentication to the current native runtime; qualification itself
does not rebind an account. Both active and inactive owned accounts qualify for
service cleanup. A stale runtime, changed role, archived account or production
target cannot use an existing browser session. Noninteractive and API-key
authentication refuse; the password session endpoint intentionally supports the
service's scripted browser login and retains native checks.
The addon stores only nonsecret ownership/runtime facts. Launchplane retains
encrypted secrets, activation, rotation, API-key removal and cleanup authority.
Service activation and active password rebinds use Odoo's own asset pregeneration, including RTL CSS
for the account's language, in the caller's transaction. It disables optional
OdooBot onboarding so first bootstrap cannot create chats or messages. Failed
preparation propagates to the native consumer; this addon never commits.

For the QA actor, HTTP requests require native readonly classification, with
the native web-client bootstrap admitted separately. Reports, printing, server
actions, imports, exports and button execution refuse before dispatch. Admitted
requests execute through PostgreSQL's read-only connection pool without Odoo's
writable fallback, including after a commit. ORM create/write/delete also refuse
for the QA actor, including sudo and user switches inside its HTTP request. Reports and server actions
have direct server guards. Native login logging/timezone bookkeeping has a
private scoped exception; user settings are initialized during service preparation.
Ordinary users retain native behavior. This trusts image-owned readonly methods
to avoid external effects; readonly classification is not permission to add an
external call to a read method. Copied production data must pass the product's
credential sanitizer before serving, independently of this addon.

Run this addon's complete native tests through the repository's focused
`qualityGate.test.local` selection. `test_policy.py` also runs without Odoo via
`uv run --no-project python -m unittest discover -s launchplane_readonly/tests -p test_policy.py`.
Native tests cover identity reuse/collisions, production/copy/generation
refusal, legacy credentials, RPC/ORM/sudo writes, preference changes, reports,
server actions and the real PostgreSQL read-only dispatch backstop. Tenant
tests own stock/scanner/chatter/printing integration and the exact read surface.
HTTP dispatch reuses a native read-only request cursor or obtains and verifies
a native read-only registry cursor. A writable fallback is closed and replaced
by the strict read-only pool. This preserves Odoo's native TestCursor and
uncommitted HttpCase fixtures without weakening PostgreSQL enforcement. Native
UI qualification must cover the installed app set, cold assets and session/device
bookkeeping. Native pregeneration does not cover every dynamic/debug/website
asset variant, and generated error CSS is not a successful frontend check.
The service browser refuses websockets; live updates are outside this read-only
surface. Missing assets do not grant QA a cache-write exception.
Source tests do not establish actual CM preview activation or authenticated QA.
