# House Standard

Inherit the root AGENTS.md. This addon turns on what every product shares from
the base image. Prefer, in order: native Odoo 20 settings and views, OCA, MuK,
then our own code, built only from behaviour specs and screenshots, never from
Odoo Enterprise source. Install-time defaults stay in `noupdate` data so a
user's or admin's later choice survives upgrades.
