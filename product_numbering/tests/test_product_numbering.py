from odoo import Command
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestProductNumbering(TransactionCase):
    def setUp(self) -> None:
        super().setUp()
        self.sequence = self.env.ref("product_sequence.seq_product_auto")
        self.sequence.write({"prefix": False, "padding": 0, "number_next_actual": 100001})
        self.template_model = self.env["product.template"]

    def test_next_skips_reference_and_barcode_in_other_companies(self) -> None:
        company = self.env["res.company"].create({"name": "Other company"})
        self.template_model.create(
            [
                {"name": "Archived reference", "default_code": "100001", "active": False, "company_id": company.id},
                {"name": "Barcode only collision", "default_code": "LEGACY", "barcode": "100002", "company_id": company.id},
            ]
        )
        self.sequence.product_number_as_barcode = True
        part = self.template_model.create({"name": "New part"})
        self.assertEqual((part.default_code, part.barcode), ("100003", "100003"))
        self.assertEqual(self.sequence.number_next_actual, 100004)

    def test_explicit_numbers_and_barcodes_in_batch_use_no_sequence_values(self) -> None:
        self.sequence.product_number_as_barcode = True
        first, second = self.template_model.create(
            [
                {"name": "Imported", "default_code": "SRC-IDENTIFIER", "barcode": "SRC-IDENTIFIER"},
                {"name": "Manually numbered", "default_code": "MANUAL", "barcode": "EXTERNAL-BARCODE"},
            ]
        )
        self.assertEqual((first.default_code, first.barcode), ("SRC-IDENTIFIER", "SRC-IDENTIFIER"))
        self.assertEqual((second.default_code, second.barcode), ("MANUAL", "EXTERNAL-BARCODE"))
        self.assertEqual(self.sequence.number_next_actual, 100001)

    def test_manual_barcode_kept_when_new_reference_is_generated(self) -> None:
        self.sequence.product_number_as_barcode = True
        part = self.template_model.create({"name": "Manually scanned", "barcode": "MANUAL-BARCODE"})
        self.assertEqual((part.default_code, part.barcode), ("100001", "MANUAL-BARCODE"))

    def test_gap_mode_fills_lowest_gap_without_advancing_counter(self) -> None:
        self.template_model.create(
            [
                {"name": "Occupied floor", "default_code": "8000"},
                {"name": "Occupied barcode", "default_code": "LEGACY", "barcode": "8002"},
            ]
        )
        self.sequence.write({"product_number_mode": "lowest_free", "product_number_floor": 8000})
        allocated = self.template_model.create([{"name": "First gap"}, {"name": "Second gap"}])
        self.assertEqual(allocated.mapped("default_code"), ["8001", "8003"])
        self.assertFalse(any(allocated.mapped("barcode")))
        self.assertEqual(self.sequence.number_next_actual, 100001)

    def test_explicit_create_and_write_follow_native_identifier_rules(self) -> None:
        first, second = self.template_model.create(
            [{"name": "First source part", "default_code": "100001"}, {"name": "Second source part", "default_code": "100001"}]
        )
        second.barcode = first.default_code
        self.assertEqual(first.default_code, second.default_code)
        self.assertEqual(second.barcode, "100001")
        self.assertEqual(self.sequence.number_next_actual, 100001)
        generated = self.template_model.create({"name": "Next available number"})
        self.assertEqual(generated.default_code, "100002")

    def test_variant_batch_skips_the_independent_template_barcode(self) -> None:
        attribute = self.env["product.attribute"].create({"name": "Color"})
        values = self.env["product.attribute.value"].create(
            [{"name": name, "attribute_id": attribute.id} for name in ("Red", "Blue")]
        )
        self.sequence.product_number_as_barcode = True
        template = self.template_model.create(
            {
                "name": "Part with variants",
                "barcode": "100001",
                "attribute_line_ids": [Command.create({"attribute_id": attribute.id, "value_ids": [Command.set(values.ids)]})],
            }
        )
        variants = template.product_variant_ids
        self.assertEqual(template.barcode, "100001")
        self.assertEqual(set(variants.mapped("default_code")), {"100002", "100003"})
        self.assertEqual(variants.mapped("default_code"), variants.mapped("barcode"))

    def test_one_attribute_value_keeps_explicit_identifiers(self) -> None:
        attribute = self.env["product.attribute"].create({"name": "Finish"})
        value = self.env["product.attribute.value"].create({"name": "Matte", "attribute_id": attribute.id})
        self.sequence.product_number_as_barcode = True
        template = self.template_model.create(
            {
                "name": "Numbered part with one finish",
                "default_code": "MANUAL-PART",
                "barcode": "MANUAL-SCAN",
                "attribute_line_ids": [Command.create({"attribute_id": attribute.id, "value_ids": [Command.link(value.id)]})],
            }
        )
        variant = template.product_variant_id
        self.assertEqual((variant.default_code, variant.barcode), ("MANUAL-PART", "MANUAL-SCAN"))
        self.assertEqual(self.sequence.number_next_actual, 100001)

    def test_explicit_regeneration_skips_occupied_numbers_and_keeps_old_barcode(self) -> None:
        self.sequence.product_number_as_barcode = True
        self.template_model.create({"name": "Existing number", "default_code": "100001"})
        template = self.template_model.create({"name": "Legacy part", "default_code": "LEGACY-PART", "barcode": "LEGACY-SCAN"})
        template.default_code = "/"
        self.assertEqual((template.default_code, template.barcode), ("100002", "LEGACY-SCAN"))
        self.assertEqual(template.product_variant_id.default_code, "100002")

    def test_slash_on_create_issues_one_reference_and_matching_barcode(self) -> None:
        self.sequence.product_number_as_barcode = True
        template = self.template_model.create({"name": "Number requested on create", "default_code": "/"})
        self.assertEqual((template.default_code, template.barcode), ("100001", "100001"))
        self.assertEqual(self.sequence.number_next_actual, 100002)

    def test_renumbering_archived_variant_keeps_active_siblings_reference(self) -> None:
        attribute = self.env["product.attribute"].create({"name": "Size"})
        values = self.env["product.attribute.value"].create(
            [{"name": name, "attribute_id": attribute.id} for name in ("Small", "Large")]
        )
        template = self.template_model.create(
            {
                "name": "Part with archived sibling",
                "attribute_line_ids": [Command.create({"attribute_id": attribute.id, "value_ids": [Command.set(values.ids)]})],
            }
        )
        archived, active = template.product_variant_ids
        original_active_number = active.default_code
        archived.active = False
        archived.default_code = "/"
        self.assertEqual(archived.default_code, "100003")
        self.assertEqual(active.default_code, original_active_number)
