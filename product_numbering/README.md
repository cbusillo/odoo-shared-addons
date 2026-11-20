# Product Numbering

Install `product_numbering` using an Odoo 20 image that includes OCA
`product_sequence`. The addon uses the OCA product sequence and any configured
category sequences. Configure the sequence under **Settings → Technical →
Sequences**.

- **Next number** advances the existing sequence, skipping occupied references
  and barcodes. Set **Next Number** once when adopting it.
- **Lowest free number** fills the first gap at or above **Lowest Product
  Number**. It leaves the sequence counter alone.
- **Use Product Number as Barcode** sets the same value on a new product that
  has no supplied barcode. A supplied reference or barcode is preserved.
  Enter `/` as the internal reference to request a new number explicitly.

Use an empty prefix and zero padding for short plain numbers. The addon clears
the unused stock OCA prefix and padding on first install. It keeps existing
sequence formatting once the counter has advanced. Date ranges are unavailable
for product numbering because they start a new counter.

Archived products, shared products, and products in other companies reserve
their internal references and primary barcodes. Existing values stay in place
when editing unrelated product information. An ordinary module update retains
the configured mode, format, barcode behavior, and counter. A supported
database restore restores those settings and the counter saved in that backup.

Before first installing OCA Product Sequence on a populated target, check the
current target's products with SQL NULL or a literal `/` internal reference
and verify reprints on a disposable copy. OCA's one-time install hook assigns
a reference to those rows and leaves their barcodes untouched. A row with a
barcode can therefore have different reference text when its label is
reprinted. Start adoption after verifying that the product's existing numbers
and label contents are preserved.
