from collections.abc import Iterator
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

    def _available_product_numbers(self, reserved: set[str]) -> Iterator[str]:
        self.ensure_one()
        products = self.env["product.product"]
        if self.product_number_mode == "lowest_free":
            if self.product_number_floor < 1:
                raise ValidationError(self.env._("The lowest product number must be positive."))
            numbers = (self.get_next_char(number) for number in count(self.product_number_floor))
            while True:
                candidates = list(islice(numbers, GAP_SEARCH_BATCH))
                occupied = products._occupied_product_numbers(candidates)
                yield from (number for number in candidates if number not in occupied and number not in reserved)
        if self.implementation == "no_gap" and not self.number_increment:
            raise ValidationError(self.env._("The product sequence step must be nonzero to skip occupied numbers."))
        while number := self.next_by_id():
            if number not in reserved and not products._occupied_product_numbers([number]):
                yield number
        raise ValidationError(self.env._("The product sequence did not return a number."))
