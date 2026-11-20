from typing import Self

from odoo import api, fields, models
from odoo.exceptions import ValidationError
from odoo.tools import SQL

NUMBER_FIELDS = ("default_code", "barcode")


class ProductProduct(models.Model):
    _inherit = "product.product"

    @api.model
    def _serialize_product_number_changes(self) -> None:
        sequence = self.env.ref("product_sequence.seq_product_auto")
        self.env.cr.execute(SQL("UPDATE ir_sequence SET write_date = write_date WHERE id = %s", sequence.id))

    @api.model
    def _product_number_owners(self, numbers: list[str]) -> dict[str, set[tuple[int, int]]]:
        if not numbers:
            return {}
        domain = fields.Domain("default_code", "in", numbers) | fields.Domain("barcode", "in", numbers)
        inventory = self.sudo().with_context(active_test=False)
        variants = inventory.search_fetch(domain, [*NUMBER_FIELDS, "product_tmpl_id"])
        templates = inventory.env["product.template"].search_fetch(domain, NUMBER_FIELDS)
        owners: dict[str, set[tuple[int, int]]] = {}
        wanted = set(numbers)
        for product in variants:
            for value in wanted.intersection((product.default_code, product.barcode)):
                owners.setdefault(value, set()).add((product.product_tmpl_id.id, product.id))
        for template in templates:
            for value in wanted.intersection((template.default_code, template.barcode)):
                owners.setdefault(value, set()).add((template.id, 0))
        return owners

    @api.model
    def _occupied_product_numbers(self, numbers: list[str]) -> set[str]:
        return set(self._product_number_owners(numbers))

    @api.model
    def _check_product_number_changes(self, changes: list[tuple[int, int, set[str]]]) -> None:
        owners = self._product_number_owners(list(set().union(*(numbers for _, _, numbers in changes))))
        for template_id, variant_id, numbers in changes:
            for number in numbers:
                if any(
                    owner_template != template_id or (variant_id and owner_variant not in (0, variant_id))
                    for owner_template, owner_variant in owners.get(number, ())
                ):
                    raise ValidationError(self.env._("Product reference or barcode %(number)s is already in use.", number=number))

    @api.model
    def _allocate_product_number(
        self, values: "odoo.values.product_product", category: "odoo.model.product_category", reserved: set[str]
    ) -> "odoo.values.product_product":
        sequence = self.env["ir.sequence"].get_category_sequence_id(category)
        number = sequence._next_available_product_number(reserved)
        reserved.add(number)
        numbered = dict(values, default_code=number)
        if sequence.product_number_as_barcode and not values.get("barcode"):
            numbered["barcode"] = number
        return numbered

    @api.model_create_multi
    def create(self, vals_list: list["odoo.values.product_product"]) -> Self:
        self._serialize_product_number_changes()
        prepared = []
        reserved = {values[field] for values in vals_list for field in NUMBER_FIELDS if values.get(field)}
        templates = self.env["product.template"].browse(
            [values["product_tmpl_id"] for values in vals_list if values.get("product_tmpl_id")]
        )
        for values in vals_list:
            if values.get("default_code", "/") == "/":
                category = self.env["product.category"].browse(values.get("categ_id"))
                if not category and values.get("product_tmpl_id"):
                    category = templates.browse(values["product_tmpl_id"]).with_prefetch(templates.ids).categ_id
                values = self._allocate_product_number(values, category, reserved)
            prepared.append(values)
        products = super().create(prepared)
        self._check_product_number_changes(
            [
                (product.product_tmpl_id.id, product.id, {values[field] for field in NUMBER_FIELDS if values.get(field)})
                for product, values in zip(products, prepared, strict=True)
            ]
        )
        return products

    def write(self, vals: "odoo.values.product_product") -> bool:
        if not set(vals).intersection(NUMBER_FIELDS):
            return super().write(vals)
        self._serialize_product_number_changes()
        if vals.get("default_code") == "/":
            reserved: set[str] = set()
            for product in self:
                category = self.env["product.category"].browse(vals["categ_id"]) if "categ_id" in vals else product.categ_id
                values = dict(vals)
                values.setdefault("barcode", product.barcode)
                product.write(self._allocate_product_number(values, category, reserved))
            return True
        changes = [
            (
                product.product_tmpl_id.id,
                product.id,
                {vals[field] for field in NUMBER_FIELDS if vals.get(field) and vals[field] != product[field]},
            )
            for product in self
        ]
        result = super().write(vals)
        self._check_product_number_changes(changes)
        return result
