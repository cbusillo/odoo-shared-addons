# External IDs

Models opt in by inheriting `external.id.mixin`. Forms get an External IDs tab
and, when a button box exists, a count button that opens the record's IDs.
Existing inherited pages remain available. Set `_external_ids_auto_ui = False`
on a model to provide its own UI.

The mixin adds these nodes in `_get_view`, before Odoo postprocesses the
combined architecture. Odoo therefore applies normal access rules and includes
the injected fields and relational subviews in the metadata returned by
`get_views`. Consumers do not need to patch form metadata or add duplicate
external-ID views.

Tests cover the effective inherited architecture, client field metadata,
cache reuse, opt-out, non-form views, and browser access to the tab and count
button. Run them through the shared addon-CI runner linked in the repository
README. Tenant-specific part forms should also be checked in that tenant's
preview with synthetic records.
