from collections.abc import Iterator
from typing import Literal, Self

from odoo import api, fields, models
from odoo.tools import SQL

NUMBER_FIELDS = ("default_code", "barcode")


class ProductProduct(models.Model):
    _inherit = "product.product"

    @api.model
    def _serialize_product_number_allocation(self) -> None:
        sequence = self.env.ref("product_sequence.seq_product_auto")
        self.env.cr.execute(SQL("UPDATE ir_sequence SET write_date = write_date WHERE id = %s", sequence.id))

    @api.model
    def _occupied_product_numbers(self, numbers: list[str]) -> set[str]:
        domain = fields.Domain("default_code", "in", numbers) | fields.Domain("barcode", "in", numbers)
        inventory = self.sudo().with_context(active_test=False)
        variants = inventory.search_fetch(domain, NUMBER_FIELDS)
        templates = inventory.env["product.template"].search_fetch(domain, NUMBER_FIELDS)
        return set(numbers).intersection(
            value for records in (variants, templates) for field in NUMBER_FIELDS for value in records.mapped(field)
        )

    @api.model
    def _allocate_product_number(
        self,
        values: "odoo.values.product_product",
        category: "odoo.model.product_category",
        reserved: set[str],
        candidates_by_sequence: dict[int, Iterator[str]],
    ) -> "odoo.values.product_product":
        sequence = self.env["ir.sequence"].get_category_sequence_id(category)
        candidates = candidates_by_sequence.setdefault(sequence.id, sequence._available_product_numbers(reserved))
        number = next(candidates)
        reserved.add(number)
        numbered = dict(values, default_code=number)
        if sequence.product_number_as_barcode and not values.get("barcode"):
            numbered["barcode"] = number
        return numbered

    @api.model_create_multi
    def create(self, vals_list: list["odoo.values.product_product"]) -> Self:
        if all(values.get("default_code", "/") != "/" for values in vals_list):
            return super().create(vals_list)
        self._serialize_product_number_allocation()
        prepared = []
        candidates_by_sequence: dict[int, Iterator[str]] = {}
        reserved = {values[field] for values in vals_list for field in NUMBER_FIELDS if values.get(field)}
        templates = self.env["product.template"].browse(
            [values["product_tmpl_id"] for values in vals_list if values.get("product_tmpl_id")]
        )
        for values in vals_list:
            if values.get("default_code", "/") == "/":
                category = self.env["product.category"].browse(values.get("categ_id") or ())
                if not category and values.get("product_tmpl_id"):
                    category = templates.browse(values["product_tmpl_id"]).with_prefetch(templates.ids).categ_id
                values = self._allocate_product_number(values, category, reserved, candidates_by_sequence)
            prepared.append(values)
        return super().create(prepared)

    def write(self, vals: "odoo.values.product_product") -> Literal[True]:
        if vals.get("default_code") != "/":
            return super().write(vals)
        self._serialize_product_number_allocation()
        reserved: set[str] = set()
        for product in self:
            category = self.env["product.category"].browse(vals["categ_id"]) if "categ_id" in vals else product.categ_id
            values = dict(vals)
            values.setdefault("barcode", product.barcode)
            numbered = self._allocate_product_number(values, category, reserved, {})
            template = product.product_tmpl_id
            if template.product_variant_ids == product:
                template.default_code = numbered["default_code"]
            super(ProductProduct, product).write(numbered)
        return True
