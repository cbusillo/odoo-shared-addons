from collections import defaultdict
from collections.abc import Iterator
from typing import Literal, Self

from odoo import api, fields, models
from odoo.tools import SQL

NUMBER_FIELDS = ("default_code", "barcode")
NUMERIC_CODE_INDEX = "USING hash (ltrim(default_code, '0')) WHERE default_code ~ '^[0-9]+$'"
NUMERIC_BARCODE_INDEX = "USING hash (ltrim(barcode, '0')) WHERE barcode ~ '^[0-9]+$'"


class ProductProduct(models.Model):
    _inherit = "product.product"

    _number_code = models.Index(NUMERIC_CODE_INDEX)
    _number_barcode = models.Index(NUMERIC_BARCODE_INDEX)

    @api.model
    def _literal_slash(self) -> bool:
        return self.env["ir.config_parameter"].sudo().get_bool("product_numbering.literal_slash")

    @api.model
    def _literal_slash_on_create(self) -> bool:
        return self._literal_slash() or self.env["ir.config_parameter"].sudo().get_bool("product_numbering.literal_slash_on_create")

    @api.model
    def _product_reference_defaults(self, defaults: dict) -> dict:
        if defaults.get("default_code") == "/" and self._literal_slash_on_create():
            defaults["default_code"] = False
        return defaults

    @api.model
    def default_get(self, fields_list: list[str]) -> dict:
        return self._product_reference_defaults(super().default_get(fields_list))

    @api.model
    def _is_product_sequence_placeholder(self, code: object) -> bool:
        return super()._is_product_sequence_placeholder(code) and not self._literal_slash_on_create()

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
    def _occupied_numeric_product_numbers(self, numbers: list[str]) -> set[str]:
        queries = []
        for model in (self, self.env["product.template"]):
            model.flush_model(NUMBER_FIELDS)
            for field in NUMBER_FIELDS:
                queries.append(
                    SQL(
                        "SELECT FROM %(table)s WHERE %(field)s ~ '^[0-9]+$' AND ltrim(%(field)s, '0') = candidate",
                        table=SQL.identifier(model._table),
                        field=SQL.identifier(field),
                    )
                )
        # noinspection PyUnresolvedReferences
        occupied = SQL(" UNION ALL ").join(queries)
        query = SQL("SELECT candidate FROM unnest(%s::text[]) AS candidate WHERE EXISTS (%s)", numbers, occupied)
        return {number for (number,) in self.env.execute_query(query)}

    @api.model
    def _allocate_product_number(
        self,
        values: "odoo.values.product_product",
        sequence: "odoo.model.ir_sequence",
        reserved: defaultdict[str, set[str]],
        candidates_by_sequence: dict[int, Iterator[str]],
    ) -> "odoo.values.product_product":
        candidates = candidates_by_sequence.setdefault(sequence.id, sequence._available_product_numbers())
        numeric = sequence._uses_numeric_product_identity()
        while True:
            number = next(candidates)
            aliases = reserved[number.lstrip("0")]
            if not aliases or (not numeric and number not in aliases):
                aliases.add(number)
                break
        numbered = dict(values, default_code=number)
        if sequence.product_number_as_barcode and not values.get("barcode"):
            numbered["barcode"] = number
        return numbered

    @api.model_create_multi
    def create(self, vals_list: list["odoo.values.product_product"]) -> Self:
        if self._literal_slash_on_create():
            codes = (values.get("default_code") for values in vals_list)
            needs_numbers = [code is False or code is None or code == "" for code in codes]
        else:
            needs_numbers = [values.get("default_code", "/") == "/" for values in vals_list]
        if not any(needs_numbers):
            return super().create(vals_list)
        self._serialize_product_number_allocation()
        prepared = []
        candidates_by_sequence: dict[int, Iterator[str]] = {}
        reserved: defaultdict[str, set[str]] = defaultdict(set)
        for values in vals_list:
            for field in NUMBER_FIELDS:
                if value := values.get(field):
                    number = str(value)
                    reserved[number.lstrip("0")].add(number)
        templates = self.env["product.template"].browse(
            [values["product_tmpl_id"] for values in vals_list if values.get("product_tmpl_id")]
        )
        for values, needs_number in zip(vals_list, needs_numbers, strict=True):
            if needs_number:
                category = self.env["product.category"].browse(values.get("categ_id") or ())
                template = templates.browse(values.get("product_tmpl_id") or ()).with_prefetch(templates.ids)
                sequence = self.env["ir.sequence"].get_category_sequence_id(category or template.categ_id)
                if (
                    sequence.product_number_goods_only
                    and (values.get("type") or template.type or self.default_get(["type"]).get("type")) != "consu"
                ):
                    values = dict(values, default_code=False)
                else:
                    values = self._allocate_product_number(values, sequence, reserved, candidates_by_sequence)
            prepared.append(values)
        return super().create(prepared)

    def write(self, vals: "odoo.values.product_product") -> Literal[True]:
        if (
            vals.get("default_code") != "/"
            or self._literal_slash()
            or (self.env.context.get("numbering_create_inverse") and self._literal_slash_on_create())
        ):
            return super().write(vals)
        self._serialize_product_number_allocation()
        reserved: defaultdict[str, set[str]] = defaultdict(set)
        for product in self:
            category = self.env["product.category"].browse(vals["categ_id"]) if "categ_id" in vals else product.categ_id
            values = dict(vals)
            values.setdefault("barcode", product.barcode)
            sequence = self.env["ir.sequence"].get_category_sequence_id(category)
            numbered = self._allocate_product_number(values, sequence, reserved, {})
            template = product.product_tmpl_id
            if template.product_variant_ids == product:
                template.default_code = numbered["default_code"]
            super(ProductProduct, product).write(numbered)
        return True
