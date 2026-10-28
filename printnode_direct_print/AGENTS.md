# Personal printer routing

Inherit the root repository instructions. This addon owns personal printer
preferences, discovery, preflight and submission. Tenant addons own document
content, print triggers and their business-record authorization.

Read [README.md](README.md) before changing the Python or report adapter
contract. Keep `_resolve_printer` as the only `(current user, physical size)`
extension point. Do not add workflow, company, browser or desk routing keys.

The complete addon test modules cover authorization and transaction safety;
select this entire addon for local validation. Tests use synthetic printers
and intercept outbound transport. Never use a real PrintNode key or printer
for source validation. Native browser tests belong in `static/tests`.
