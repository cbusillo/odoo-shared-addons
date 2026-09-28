# AGENTS.md - test_support

Purpose

- Provide shared test fixtures, helpers, and base cases for reusable addons.

Scope

- Test-only helpers that belong in the addon layer and can be reused across
  tenant-neutral addons.
- No production models, runtime configuration, or tenant-specific fixture data.

Testing

- Keep helper tests close to the helper modules they validate.
- When changing discovery helpers, verify both direct unit usage and Odoo test
  discovery behavior. Discovery fails the run when a test module or package
  cannot be imported; do not turn that back into a warning.

Implementation Notes

- Avoid adding business-domain assumptions to shared fixtures; tenant repos
  should own tenant-specific records and workflows.
- Keep imports light so test support can be installed alongside focused addon
  test runs without pulling unnecessary runtime behavior.
