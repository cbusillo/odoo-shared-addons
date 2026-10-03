from odoo.api import Environment


def preserve_seed_records(env: Environment) -> None:
    """Retain existing systems and links when their install data is removed."""
    env["ir.model.data"].sudo().search(
        [
            ("module", "=", "external_ids"),
            ("model", "in", ("external.system", "external.system.url")),
            ("noupdate", "=", False),
        ]
    ).write({"noupdate": True})
