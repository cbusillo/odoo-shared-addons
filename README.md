# Shared Addons

Purpose

- Hold reusable cross-client addons consumed by tenant workspaces.

Rules

- Shared addons must not depend on tenant-specific addons.
- If a client addon becomes reusable, promote it here.
- Keep tenant-specific addons in tenant repos. Promote code here only when it
  is genuinely reusable across clients.

Addon Inventory

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
- `test_support`: shared fixtures, test helpers, and recorded tour support.
- `transaction_utilities`: transaction and cron runtime-budget helpers.
