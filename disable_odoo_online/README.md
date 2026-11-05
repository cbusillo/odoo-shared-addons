# Disable Odoo Online

For self-hosted Odoo 20 Community, skip the publisher-warranty phone-home call.
`publisher_warranty.contract.update_notification()` returns `True` in both cron
modes without calling upstream or writing settings. Other network requests,
banners and upsells retain their native behavior.

Install `disable_odoo_online` with its native `base` and `mail` dependencies.
Managed instances already require this module by name. Use this shared copy
without also declaring an external source that supplies the same module.

The Odoo integration test checks both cron modes with requests-library HTTP
calls blocked. Run it through this repository's focused addon-test command,
selecting `disable_odoo_online`; see the root README for preparation.
