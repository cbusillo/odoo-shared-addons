from itertools import count, islice

from odoo import fields, models
from odoo.exceptions import ValidationError

GAP_SEARCH_BATCH = 128


class IrSequence(models.Model):
    _inherit = "ir.sequence"

    product_number_mode = fields.Selection(
        [("next", "Next number"), ("lowest_free", "Lowest free number")],
        default="next",
        required=True,
    )
    product_number_floor = fields.Integer(string="Lowest Product Number", default=1)
    product_number_as_barcode = fields.Boolean(string="Use Product Number as Barcode")

    def _next_available_product_number(self, reserved: set[str]) -> str:
        self.ensure_one()
        if self.use_date_range or self.number_increment < 1:
            raise ValidationError(self.env._("Product numbering requires a positive increment and no date ranges."))
        products = self.env["product.product"]
        if self.product_number_mode == "lowest_free":
            if self.product_number_floor < 1:
                raise ValidationError(self.env._("The lowest product number must be positive."))
            numbers = (self.get_next_char(number) for number in count(self.product_number_floor))
            while True:
                candidates = list(islice(numbers, GAP_SEARCH_BATCH))
                occupied = reserved | products._occupied_product_numbers(candidates)
                if available := next((number for number in candidates if number not in occupied), None):
                    return available
        while number := self.next_by_id():
            if number not in reserved and not products._occupied_product_numbers([number]):
                return number
        raise ValidationError(self.env._("The product sequence did not return a number."))
