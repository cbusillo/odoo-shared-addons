from typing import Self

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
        return super(ProductTemplate, self.with_context(numbering_template_create=True)).create(vals_list).with_env(self.env)

    def _prepare_variant_values(self, combination: "odoo.model.product_template_attribute_value") -> "odoo.values.product_product":
        vals = super()._prepare_variant_values(combination)
        if self.env.context.get("numbering_template_create") and all(
            len(line.product_template_value_ids._only_active()) == 1 for line in combination.attribute_line_id
        ):
            for field in NUMBER_FIELDS:
                if self[field]:
                    vals[field] = self[field]
        return vals
