# Shared Addons

Purpose

- Hold reusable cross-client addons consumed by tenant workspaces.

Rules

- Shared addons must not depend on tenant-specific addons.
- If a client addon becomes reusable, promote it here.
- Keep tenant-specific addons in tenant repos. Promote code here only when it
  is genuinely reusable across clients.
