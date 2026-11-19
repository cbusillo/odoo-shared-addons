# Environment Banner Context

Shared warning in the Odoo backend for non-production lanes. See the
[README](README.md) for the runtime contract.

Keep the lane decision in `models/ir_http.py`. The web client receives only the
visibility flag. Use the browser tests to verify the warning through Odoo's
session and web client.
