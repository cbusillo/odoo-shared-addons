# AGENTS.md — discuss_record_links

Purpose

- Add message shortcuts to underlying business records in Discuss/Chatter.

Scope

- Discuss thread tools and mail.message links to Odoo models.

Testing

- Unit: link generation; access rules respected.
- Tours: the insert tour checks for a record-link anchor; the label and
  record-ID label tours check for labeled anchors without asserting the expected
  label text. A smoke tour covers opening Discuss.

Implementation Notes

- Respect Odoo access rules when generating record links; non-admin users must
  not receive shortcuts to records they cannot read.
- The `/discuss_record_links/search` and `/labels` routes are for internal
  users only and run with the caller's rights (no `sudo`). `/labels` labels
  only configured models and omits records the caller cannot read; the client
  labels other internal links through the user's own ORM `read`.
- Validate browser or tour behavior through an assembled workspace or tenant
  environment when Discuss web-client behavior is involved.
