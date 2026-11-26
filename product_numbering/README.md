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

By default, entering `/` requests a new number when creating a product or
editing an existing single-variant product or variant. Two database Boolean
parameters let consumers pass explicitly supplied slashes to their own
validation and imports:

- Set `product_numbering.literal_slash` to true for both creates and edits,
  including update imports.
- Set only `product_numbering.literal_slash_on_create` to true for creates.
  Edits still request a new number.

With either option, omitted and empty references on new goods use the
configured allocator. Both parameters default to false.
Literal-slash mode requires a packaged `product_sequence` with the
`_is_product_sequence_placeholder` hook on both variant create and write.

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

Older images with the original OCA pre-install hook assign placeholder
references to existing blank and slash variants. On a populated database,
use a package that preserves existing references on first install.
