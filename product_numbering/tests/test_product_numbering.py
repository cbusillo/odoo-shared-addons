from unittest.mock import patch

from odoo import Command, api
from odoo.exceptions import ValidationError
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
        other = self.env["res.company"].create({"name": "Other catalogue"})
        archived, legacy = self.template_model.create(
            [
                {"name": "Occupied floor", "default_code": "8000", "company_id": other.id, "active": False},
                {"name": "Occupied barcode", "default_code": "SKU-8001", "barcode": "0008002"},
            ]
        )
        self.sequence.write(
            {"product_number_mode": "lowest_free", "product_number_floor": 8000, "padding": 6, "product_number_as_barcode": True}
        )
        first, second, manual = self.env["product.product"].create(
            [
                {"name": "First gap"},
                {"name": "Second gap", "barcode": "EXTERNAL-SCAN"},
                {"name": "Explicit batch identifiers", "default_code": "08003", "barcode": "8004"},
            ]
        )
        self.assertEqual((first.default_code, second.default_code), ("008001", "008005"))
        self.assertEqual(first.barcode, first.default_code)
        self.assertEqual(second.barcode, "EXTERNAL-SCAN")
        self.assertEqual((manual.default_code, manual.barcode), ("08003", "8004"))
        self.assertEqual((archived.default_code, legacy.default_code, legacy.barcode), ("8000", "SKU-8001", "0008002"))
        self.assertEqual(self.sequence.number_next_actual, 100001)

    def test_automatic_numbering_can_be_limited_to_goods(self) -> None:
        numbered_service = self.template_model.create({"name": "Numbered service", "type": "service"})
        self.assertTrue(numbered_service.default_code)
        self.sequence.product_number_goods_only = True
        self.sequence.product_number_as_barcode = True
        choice = self.env["product.combo"].create(
            {"name": "Services", "combo_item_ids": [Command.create({"product_id": numbered_service.product_variant_id.id})]}
        )
        service, combo, goods = self.template_model.create(
            [
                {"name": "Repair service", "type": "service", "barcode": "REPAIR"},
                {"name": "Bundle", "type": "combo", "combo_ids": [Command.link(choice.id)]},
                {"name": "Part"},
            ]
        )
        self.assertEqual((service.default_code, service.barcode), (False, "REPAIR"))
        self.assertFalse(combo.default_code)
        self.assertFalse(combo.barcode)
        service_variant = self.env["product.product"].with_context(default_type="service").create({"name": "Service variant"})
        self.assertFalse(service_variant.default_code)
        direct_goods = self.env["product.product"].create({"name": "Goods variant"})
        self.assertEqual((direct_goods.default_code, direct_goods.barcode), ("100003", "100003"))
        self.assertEqual((goods.default_code, goods.barcode), ("100002", "100002"))

    def test_prefixed_gap_numbers_reserve_the_exact_identifier(self) -> None:
        self.sequence.write(
            {
                "product_number_mode": "lowest_free",
                "product_number_floor": 7,
                "prefix": "P",
                "padding": 3,
                "product_number_as_barcode": False,
            }
        )
        self.template_model.create(
            [
                {"name": "Other format", "default_code": "P7", "barcode": "7"},
                {"name": "Same format", "default_code": "P008"},
            ]
        )
        parts = self.template_model.create([{"name": "First"}, {"name": "Second"}])
        self.assertEqual(parts.mapped("default_code"), ["P007", "P009"])
        self.assertFalse(any(parts.mapped("barcode")))

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

    def test_manual_create_and_configured_edit_validate_literal_reference(self) -> None:
        self.env["ir.config_parameter"].sudo().set_bool("product_numbering.literal_slash_on_create", True)

        @api.constrains("default_code")
        def validate_reference(templates: "odoo.model.product_template") -> None:
            if "/" in templates.mapped("default_code"):
                raise ValidationError(templates.env._("Use a catalogue reference."))

        constraints = [*self.template_model._constraint_methods, validate_reference]
        with patch.object(type(self.template_model), "_constraint_methods", constraints):
            part = self.template_model.create({"name": "Automatic reference"})
            variant = part.product_variant_id
            original = part.default_code
            self.assertTrue(original)
            with self.assertRaisesRegex(ValidationError, "Use a catalogue reference"):
                self.template_model.create({"name": "Typed reference", "default_code": "/"})

            self.env["ir.config_parameter"].sudo().set_bool("product_numbering.literal_slash", True)
            with self.assertRaisesRegex(ValidationError, "Use a catalogue reference"):
                part.write({"default_code": "/"})
            self.env.invalidate_all()
            self.assertEqual((part.default_code, variant.default_code), (original, original))

    def test_import_create_keeps_literal_reference_in_a_mixed_batch(self) -> None:
        self.env["ir.config_parameter"].sudo().set_bool("product_numbering.literal_slash_on_create", True)
        self.sequence.product_number_as_barcode = True
        variants = self.env["product.product"].create(
            [
                {"name": "No reference supplied"},
                {"name": "Literal source reference", "default_code": "/", "barcode": "SOURCE-SCAN"},
                {"name": "Empty reference", "default_code": False},
                {"name": "Empty text", "default_code": ""},
            ]
        )
        self.assertEqual(variants.mapped("default_code"), ["100001", "/", "100002", "100003"])
        self.assertEqual(variants.mapped("barcode"), ["100001", "SOURCE-SCAN", "100002", "100003"])
        self.assertEqual(variants.product_tmpl_id.mapped("default_code"), variants.mapped("default_code"))
        variants[1].default_code = "/"
        self.assertEqual((variants[1].default_code, variants[1].barcode), ("100004", "SOURCE-SCAN"))

    def test_literal_reference_can_be_supplied_on_create_and_variant_edit(self) -> None:
        self.env["ir.config_parameter"].sudo().set_bool("product_numbering.literal_slash", True)
        products = self.env["product.product"]
        defaults = products.default_get(["default_code"])
        generated, literal = products.create([dict(defaults, name="Form default"), {"name": "Typed slash", "default_code": "/"}])
        self.assertEqual((generated.default_code, literal.default_code), ("100001", "/"))
        templates = self.template_model.with_context(default_default_code="/").create(
            [{"name": "Blank template"}, {"name": "Literal template", "default_code": "/"}]
        )
        self.assertEqual(templates.mapped("default_code"), ["100002", "/"])
        self.assertEqual(templates.product_variant_id.mapped("default_code"), ["100002", "/"])

        generated.write({"default_code": "/"})
        self.env.invalidate_all()
        self.assertEqual(generated.default_code, "/")

    def test_template_create_inverse_keeps_literal_until_a_later_renumber(self) -> None:
        self.env["ir.config_parameter"].sudo().set_bool("product_numbering.literal_slash_on_create", True)
        template = self.template_model.create(
            {"name": "Supplied variant", "default_code": "/", "product_variant_ids": [Command.create({"default_code": "SOURCE"})]}
        )
        self.assertEqual((template.default_code, template.product_variant_id.default_code), ("/", "/"))
        template.default_code = "/"
        self.assertEqual((template.default_code, template.product_variant_id.default_code), ("100001", "100001"))

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
