# Environment Banner

The Odoo backend shows “This is not production. Data you enter here can be
lost.” on testing, previews, local development and any other non-production
lane.

The addon reads the Odoo process's `PLATFORM_INSTANCE`. Launchplane sets it
for deployed lanes, and Odoo Devkit sets it for local runtimes. Only `prod`
hides the banner. A missing, blank or unrecognized value shows it.

Existing `environment_banner.enabled` and
`environment_banner.production_hostnames` database parameters have no effect.
