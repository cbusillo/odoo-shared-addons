# Environment Banner Context

Shared backend banner for non-production environments.

## Key Files

- `static/src/js/environment_banner.js`
- `static/src/xml/environment_banner.xml`
- `static/src/scss/environment_banner.scss`
- `models/ir_http.py` (session_info config injection)

## Configuration

- `environment_banner.enabled` (default True)
- `environment_banner.production_hostnames` (comma or whitespace-separated hostnames)

## Implementation Notes

- Keep banner behavior tenant-neutral; do not encode client-specific hostname
  policy beyond the configurable production hostname list.
- Keep JavaScript small and Odoo-service oriented, with browser validation
  routed through the assembled workspace or tenant environment when behavior
  depends on the web client.
