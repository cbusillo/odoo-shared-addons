# AGENTS.md — discuss_record_links

Purpose

- Add message shortcuts to underlying business records in Discuss/Chatter.

Scope

- Discuss thread tools and mail.message links to Odoo models.

Testing

- Unit: link generation; access rules respected.
- Tour: open a record from Discuss and verify view loads.

Implementation Notes

- Respect Odoo access rules when generating record links; non-admin users must
  not receive shortcuts to records they cannot read.
- Validate browser or tour behavior through an assembled workspace or tenant
  environment when Discuss web-client behavior is involved.
