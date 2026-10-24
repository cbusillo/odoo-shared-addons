# Launchplane settings

This addon applies Launchplane's typed override payload inside Odoo. Launchplane
owns the payload and runtime configuration; this addon applies what the process
receives.

## Pure installed payload contract

`services/override_payload.py` is a self-contained standard-library module. A
verified reader can load that exact file directly without importing the addon,
Odoo or a database client. Module initialization reads no environment, files or
runtime state. The native adapter delegates to the same implementation.

- `decode_payload(encoded)` accepts a base64-encoded UTF-8 JSON object. Empty or
  whitespace input returns `None`; malformed encoding, JSON or a non-object
  root raises `OverridePayloadError`.
- `resolve_config_parameters(payload, environment, *, keys=None)` accepts the
  output of `decode_payload` and returns only
  the supplied `config_parameters` entries, using the explicit environment
  mapping. `None`, absent entries or an empty list project no parameters.
- Keys are stripped and lowercased, including names in the optional `keys`
  collection. A bare string/bytes value, non-string element or blank name is
  rejected. With a selection, only matching keys have their environment
  references resolved. Every entry still receives environment-free value
  validation: value object, supported source, literal value presence and
  nonempty referenced variable name, alongside list/item and key validation.
  With no selection, every entry resolves in order. Duplicate normalized keys
  retain their last value and their first insertion position; an invalid earlier
  entry still fails even when a later entry would replace it.
- Literal normalization retains the native applier's semantics; see the module
  for the exact boolean vocabulary and scalar conversion. Secret-bound values
  come from the named environment variable
  exactly as stored, including whitespace and empty strings. Missing variables
  or unsupported value sources raise `OverridePayloadError`.

Config-parameter projection, with or without `keys`, does not prove that the
complete payload was accepted or applied. Neither mode validates `addon_settings`
or later Shopify and Authentik application. Selected projection also leaves
unselected environment references unresolved. Readers must keep acceptance and
application unknown unless separately established. The native applier uses no
selection and continues to resolve every config-parameter entry.

The ORM compatibility entrypoints retain Odoo `ValidationError` and the existing
messages. Shopify and Authentik continue through their existing adapters. No
payload limits, defaults, environment policy or application order change here.

Projection does not read, inherit, overlay or clear existing Odoo parameters.
The applier writes only projected keys, so omission leaves an existing parameter
untouched. A reader must preserve that distinction when comparing payload intent
with database state.

Returned mappings can contain credentials. Keep them inside the consuming
process; never log, serialize, export or return them from an operational read.
This producer grants no runtime access and makes no connection. Operational
readers must separately verify installed-file/artifact provenance, select fixed
keys, impose their own transport bounds and keep unresolved evidence unknown.

The standalone `tests/unit/test_override_payload.py` loads the pure file without
Odoo. Native discovery also runs those cases and
`test_override_payload_integration.py` through the addon test harness.
