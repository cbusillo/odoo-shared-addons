# AGENTS.md - notification_permission_patch

Purpose

- Keep Odoo browser notification subscriptions aligned with browser permission
  changes.

Scope

- Web-client patching around notification permission observation.
- JavaScript unit tests for permission APIs, cleanup, and unsupported-browser
  behavior.

Testing

- Cover PermissionStatus event-listener and `onchange` paths, denied/granted
  transitions, component teardown cleanup, and browsers without Permissions API
  support.

Implementation Notes

- Keep the patch defensive because browser permission implementations vary.
- Do not add tenant-specific notification policy here; runtime notification
  settings belong in assembled workspaces or tenant repos.
