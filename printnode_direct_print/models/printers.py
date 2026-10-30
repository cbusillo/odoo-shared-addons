from odoo import api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError

from ..transport import Rejected, Unconfirmed


def physical_size(paperformat: "odoo.model.report_paperformat") -> tuple[int, int]:
    paperformat.ensure_one()
    size = sorted((round(paperformat.print_page_width * 10), round(paperformat.print_page_height * 10)))
    if size[0] <= 0:
        raise ValidationError(paperformat.env._("%(paper)s has no physical paper size.", paper=paperformat.display_name))
    return size[0], size[1]


class PrintNodePrinter(models.Model):
    _name = "printnode.printer"
    _description = "Discovered printer"

    name = fields.Char(required=True)
    external_id = fields.Integer(required=True)
    _external_uniq = models.Constraint("unique(external_id)", "This printer is already listed.")

    @api.model
    def action_discover(self) -> dict:
        routing = self.env["printnode.routing"]
        routing._check_actor()
        try:
            printers = routing._client().printers()
        except (Rejected, Unconfirmed) as error:
            raise UserError(
                self.env._("Printer discovery failed. Your saved choices are unchanged; try discovery later.")
            ) from error
        catalog = self.sudo()
        for printer in printers:
            name = f"{printer['name']} on {printer['computer']['name']}"
            existing = catalog.search([("external_id", "=", printer["id"])], limit=1)
            if existing:
                existing.name = name
            else:
                catalog.create({"external_id": printer["id"], "name": name})
        return {"type": "ir.actions.client", "tag": "reload"}


class PrintNodePreference(models.Model):
    _name = "printnode.preference"
    _description = "Personal printer"
    _rec_name = "size_label"

    user_id = fields.Many2one("res.users", required=True, default=lambda self: self.env.user, ondelete="cascade")
    paperformat_id = fields.Many2one(
        "report.paperformat", domain=lambda self: self._paperformat_domain(), string="Paper size", required=True, ondelete="restrict"
    )
    size_label = fields.Char(compute="_compute_size_label", string="Physical size")
    width = fields.Integer(compute="_compute_size", store=True)
    height = fields.Integer(compute="_compute_size", store=True)
    printer_id = fields.Many2one("printnode.printer", required=True, ondelete="restrict", string="Printer")
    _user_size_uniq = models.Constraint("unique(user_id, width, height)", "You already have a printer for this paper size.")

    @api.model
    def _paperformat_domain(self) -> list:
        choices = {}
        for paper in self.env["report.paperformat"].search([], order="id"):
            if paper.print_page_width <= 0 or paper.print_page_height <= 0:
                continue
            size = physical_size(paper)
            choices.setdefault(size, paper.id)
        return [("id", "in", list(choices.values()))]

    @api.depends("paperformat_id")
    def _compute_size(self) -> None:
        for preference in self:
            if not preference.paperformat_id:
                preference.width = preference.height = 0
                continue
            preference.width, preference.height = physical_size(preference.paperformat_id)

    @api.depends("width", "height", "paperformat_id.format")
    def _compute_size_label(self) -> None:
        for preference in self:
            label = f"{preference.width / 10:g} × {preference.height / 10:g} mm"
            if preference.paperformat_id.format not in (False, "custom"):
                label = f"{preference.paperformat_id.format} ({label})"
            preference.size_label = label

    def _check_owners(self, user_ids: list[int]) -> None:
        if not self.env.user.has_group("base.group_system") and any(user_id != self.env.uid for user_id in user_ids):
            raise AccessError(self.env._("You can change only your own printers."))

    @api.model_create_multi
    def create(self, vals_list: list[dict]) -> "odoo.model.printnode_preference":
        default_user = self.default_get(["user_id"]).get("user_id", self.env.uid)
        self._check_owners([values.get("user_id", default_user) for values in vals_list])
        for values in vals_list:
            values.pop("width", None)
            values.pop("height", None)
        return super().create(vals_list)

    def write(self, values: dict) -> bool:
        self._check_owners(self.user_id.ids + ([values["user_id"]] if "user_id" in values else []))
        values = {key: value for key, value in values.items() if key not in ("width", "height")}
        return super().write(values)

    def unlink(self) -> bool:
        self._check_owners(self.user_id.ids)
        return super().unlink()

    @api.model
    def action_my_printers(self) -> dict:
        self.env["printnode.routing"]._check_actor()
        return {
            "type": "ir.actions.act_window",
            "name": self.env._("My printers"),
            "res_model": self._name,
            "view_mode": "list,form",
            "views": [(False, "list"), (False, "form")],
            "domain": [("user_id", "=", self.env.uid)],
            "context": {"default_user_id": self.env.uid},
        }
