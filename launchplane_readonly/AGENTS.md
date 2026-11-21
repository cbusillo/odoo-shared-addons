# launchplane_readonly

Reusable Odoo 20 read-only access for staff and qualified QA identities. Tenant
addons own staff role mapping, read permissions, menus and preview-fixture
delivery. Launchplane owns QA credentials and activation.

Keep ownership and authentication bindings private and credential-free. Never
adopt staff accounts or infer ownership from a login. Qualify native runtime
identity, database and testing-copy witnesses before creating or reusing a shell.
Keep authentication bookkeeping separate from business-write permission.

Run the complete addon test modules for any guard or identity change, including
real Odoo HTTP and ORM refusal tests. Use the staff observer tests for mixed-role reads and native write controls.
Ordinary users retain their behavior.
