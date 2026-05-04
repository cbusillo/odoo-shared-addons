# AGENTS.md - launchplane_settings

Purpose

- Apply Launchplane-managed instance override payloads to Odoo settings.

Scope

- Decode and validate the runtime override payload.
- Apply shared Odoo config parameters and delegate addon-specific settings to
  reusable addon adapters.
- No ownership of canonical runtime values, deploy orchestration, or tenant
  release policy.

Testing

- Cover malformed payloads, unsupported sources, missing secret-bound
  environment variables, boolean normalization, and addon-specific delegation.
- Include clear/apply paths for optional integrations such as Shopify when those
  payload rules change.

Implementation Notes

- `launchplane` owns the authoritative runtime payload; this addon only applies
  values that arrive in the Odoo process.
- Fail loudly for invalid override payloads, but keep absent optional addon
  adapters as no-ops so this addon stays reusable.
