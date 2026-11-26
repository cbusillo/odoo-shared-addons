# Product Numbering

Install `product_numbering` using an Odoo 20 image that includes OCA
`product_sequence`. The addon uses the OCA product sequence and any configured
category sequences. Configure the sequence under **Settings → Technical →
Sequences**.

- **Next number** advances the existing sequence, skipping occupied references
  and barcodes. Set **Next Number** once when adopting it.
- **Lowest free number** fills the first gap at or above **Lowest Product
  Number**. With an empty prefix and suffix, digit-only references and barcodes
  reserve the same number at every padding width. For example, an archived
  reference of `8000` reserves `008000` when padding is six. A prefix or
  suffix uses exact matching. The sequence counter stays in place.
- **Automatically Number Goods Only** limits automatic numbering on creation
  to products of type Goods, including when a new record supplies `/`. Leave
  it off to number all product types.
- **Use Product Number as Barcode** sets the same value on a new product that
  has no supplied barcode. A supplied reference or barcode is preserved.
  On an existing single-variant product or variant, enter `/` to request a new number.

By default, entering `/` when creating a product requests a new number. Set
the database Boolean parameter `product_numbering.literal_slash_on_create`
to true when callers use `/` as source text. On creation, an explicitly
supplied slash then reaches native validation and imports as supplied.
Omitted and empty references use the configured allocator. Entering `/` on
an existing product still requests a new number.

Use an empty prefix and zero padding for short plain numbers. The addon clears
the unused stock OCA prefix and padding on first install. It keeps existing
sequence formatting once the counter has advanced. Leave date ranges off
when using one running counter.

Archived products, shared products, and products in other companies reserve
their internal references and primary barcodes. Existing values stay in place
when editing unrelated product information. Manual assignments and imports
use native product validation. An ordinary module update retains
the configured mode, format, barcode behavior, and counter. A supported
database restore restores those settings and the counter saved in that backup.

Before first installing OCA Product Sequence on a populated target, check the
current target's products with SQL NULL or a literal `/` internal reference
and verify reprints on a disposable copy. OCA's one-time install hook assigns
a reference to those rows and leaves their barcodes untouched. A row with a
barcode can therefore have different reference text when its label is
reprinted. Start adoption after verifying that the product's existing numbers
and label contents are preserved.
