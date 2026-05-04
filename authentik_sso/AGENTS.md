# AGENTS.md - authentik_sso

Purpose

- Configure Authentik OAuth2/OpenID Connect login and default group mappings for
  shared Odoo environments.

Scope

- OAuth provider setup, Authentik claim parsing, template users, and group
  mapping records.
- No tenant-specific provider URLs, secrets, rollout notes, or environment
  authority.

Testing

- Cover missing or partial provider settings, disabled-provider behavior, claim
  fallback order, and group mapping application.
- Exercise non-admin and portal-user paths when access rules or group mappings
  change.

Implementation Notes

- Runtime values come from workspace or Launchplane-managed configuration; keep
  defaults safe and non-secret in this addon.
- Treat OAuth claims as untrusted input and keep parsing tolerant of missing or
  differently named Authentik fields.
