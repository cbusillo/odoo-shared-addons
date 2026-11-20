from odoo import api


def post_init_hook(env: api.Environment) -> None:
    sequence = env.ref("product_sequence.seq_product_auto")
    if (sequence.prefix, sequence.padding, sequence.number_next_actual) == ("PR/", 5, 1):
        sequence.write({"prefix": False, "padding": 0})
