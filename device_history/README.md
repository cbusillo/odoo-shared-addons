# Historical Device Information

Odoo 19 stored parsed platform, browser and device type. Odoo 20 stores the raw
User-Agent instead. This addon preserves historical parsed values without
claiming that they reconstruct the original request string.

The original `res.device.log` columns and record IDs remain in place. The
install hook marks existing rows whose raw agent is NULL as
`legacy_user_agent_unavailable`. The raw column becomes nullable, with a
conditional database constraint requiring a raw agent on every unmarked row.
The hook runs only at installation. Ordinary request logging still inserts the
actual request agent through native code; it does not set the historical flag.

`res.device` uses the native parser when raw telemetry exists and reads stored
parsed values otherwise, through the caller's existing log access. Unknown
version and language stay unknown. Session reads follow the device chosen by
native current/latest selection, even when the session view ID identifies a
different log. Device and session forms explicitly show raw-agent unavailability.
Queries, view IDs, ACLs, revocation and cleanup remain native. NULL raw agents
do not compare equal during native deduplication, preserving distinct history.
Configured native hard retention still applies.

## Installation contract

Ship this addon in the shared source pin used to build the native Odoo 20
artifact. Append `device_history` to the workspace's `ODOO_INSTALL_MODULES`
before its first native 20 migration. Devkit's existing data-workflow command
must install it in the **same process** that updates base:

```text
odoo-bin --update all --load base,web --init <existing-init-modules>,device_history
```

Keep the consuming workspace's normal pre-upgrade script, database, addon paths
and other options. Devkit owns this command and those settings. This is an
install addition to that command, not a second run after a base-only upgrade.
The addon depends on `base`: native base initialization creates `user_agent`,
then this addon's pre-init hook marks the existing historical cohort, and its
model reflection claims the original parsed fields before end-of-load cleanup.
No SQL backfill, column rename, core patch or pre-upgrade bridge edit is needed.

Native `ir.model.fields._reflect_fields` creates this addon's XMLIDs pointing
at the existing field records. End cleanup also recognizes these fields on
their original base model and keeps the base aliases. The addon owns the field
definitions and its own XMLIDs; the original stored columns survive. Keep this
addon installed on subsequent upgrades. Do not
uninstall it while history is needed: uninstalling an owned field can drop its
column. Installation after a completed base-only 20 update cannot recover
already removed values; use the original retained migration input instead.

An early base NOT NULL warning may occur before this addon loads. The final
registry and schema, rather than that intermediate warning, decide the result.
In the consuming migration's existing full-load readback, verify the original
cohort's row IDs and parsed values, NULL raw agents and true historical flags,
the conditional constraint and final nullable raw column, this addon's field
XMLIDs, and Devices/Sessions reads as their actual users. Verify fresh request
logs carry actual raw telemetry without the historical flag and that another
user cannot read the historical cohort. This source contract does not claim
that a real migration has executed or passed.

## Tests

`tests/test_device_history.py` is imported by `tests/__init__.py`. Select this
entire addon through the repository's focused addon-CI command. Tests cover
historical device/session reads with differing view and selected-device IDs,
native current-device telemetry, missing-agent rejection, unchanged cleanup,
owner/other-user access and installation cohort marking.
