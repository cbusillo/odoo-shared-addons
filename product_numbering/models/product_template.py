from typing import Literal, Self

from odoo import api, models

from .product_product import NUMBER_FIELDS


class ProductTemplate(models.Model):
    _inherit = "product.template"

    @api.model_create_multi
    def create(self, vals_list: list["odoo.values.product_template"]) -> Self:
        vals_list = [
            {field: value for field, value in values.items() if field != "default_code"}
            if values.get("default_code") == "/"
            else values
            for values in vals_list
        ]
        products = self.env["product.product"]
        products._serialize_product_number_changes()
        templates = super(ProductTemplate, self.with_context(numbering_template_create=True)).create(vals_list).with_env(self.env)
        products._check_product_number_changes(
            [
                (
                    template.id,
                    0,
                    {values[field] for field in NUMBER_FIELDS if values.get(field)},
                )
                for template, values in zip(templates, vals_list, strict=True)
                if len(template.product_variant_ids) != 1
            ]
        )
        return templates

    def _prepare_variant_values(self, combination: "odoo.model.product_template_attribute_value") -> "odoo.values.product_product":
        vals = super()._prepare_variant_values(combination)
        if self.env.context.get("numbering_template_create") and all(
            len(line.product_template_value_ids._only_active()) == 1 for line in combination.attribute_line_id
        ):
            for field in NUMBER_FIELDS:
                if self[field]:
                    vals[field] = self[field]
        return vals

    def write(self, vals: "odoo.values.product_template") -> Literal[True]:
        if not set(vals).intersection(NUMBER_FIELDS):
            return super().write(vals)
        products = self.env["product.product"]
        products._serialize_product_number_changes()
        changes = [
            (
                template.id,
                0,
                {
                    vals[field]
                    for field in NUMBER_FIELDS
                    if vals.get(field) and (field == "barcode" or vals[field] != "/") and vals[field] != template[field]
                },
            )
            for template in self
            if len(template.product_variant_ids) != 1
        ]
        result = super().write(vals)
        products._check_product_number_changes(changes)
        return result
