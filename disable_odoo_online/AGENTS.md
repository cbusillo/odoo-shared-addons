# Disable Odoo Online

Inherit the root AGENTS.md. This addon only skips the publisher-warranty
notification call on Odoo 20 Community. Keep it free of settings writes and
unrelated network or UI changes.

The native `mail` addon owns the model and its access policy. Use the root
repository's addon-CI command to run this addon's full tests.
