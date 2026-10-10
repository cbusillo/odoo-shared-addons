# Security Policy

## Supported Versions

Security fixes target the current `main` branch. There are no separate
supported release lines.

## Reporting a Vulnerability

Report suspected vulnerabilities privately through GitHub's
[Report a vulnerability](https://github.com/cbusillo/odoo-shared-addons/security/advisories/new)
form. Do not open a public issue for a vulnerability.

Include the addon, the commit, the Odoo version, the impact, and the
smallest steps that reproduce it.

Do not send database dumps, customer data, credentials, or other personal
data. Use redacted or made-up values.

This is a single-maintainer project. Reports are handled on a best-effort
basis, and I aim to reply within seven days.

## Scope

Relevant reports include:

- access or record rules that show or change records for the wrong users;
- flaws in Authentik sign-in or group mapping;
- unsafe links, scripts, or redirects from record-link or external-ID
  features;
- settings being applied without the permission the addon expects; and
- dependency or GitHub Actions supply-chain problems.

Problems in Odoo itself should go to Odoo S.A., and problems in Authentik
should go to the Authentik project.
