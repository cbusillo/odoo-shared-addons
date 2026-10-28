from odoo import SUPERUSER_ID, api, fields, models
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
    _rec_name = "paperformat_key"

    user_id = fields.Many2one("res.users", required=True, default=lambda self: self.env.user, ondelete="cascade")
    paperformat_key = fields.Selection(selection="_paper_choices", string="Paper size", required=True)
    width = fields.Integer(compute="_compute_size", store=True)
    height = fields.Integer(compute="_compute_size", store=True)
    printer_id = fields.Many2one("printnode.printer", required=True, ondelete="restrict", string="Printer")
    _user_size_uniq = models.Constraint("unique(user_id, width, height)", "You already have a printer for this paper size.")

    @api.model
    def _paper_choices(self) -> list[tuple[str, str]]:
        choices = {}
        for paper in self.env["report.paperformat"].search([], order="id"):
            if paper.print_page_width <= 0 or paper.print_page_height <= 0:
                continue
            size = physical_size(paper)
            label = f"{size[0] / 10:g} × {size[1] / 10:g} mm"
            if paper.format != "custom":
                label = f"{paper.format} ({label})"
            choices.setdefault(size, (str(paper.id), label))
        return list(choices.values())

    @api.depends("paperformat_key")
    def _compute_size(self) -> None:
        for preference in self:
            if not preference.paperformat_key:
                preference.width = preference.height = 0
                continue
            paper = self.env["report.paperformat"].browse(int(preference.paperformat_key)).exists()
            preference.width, preference.height = physical_size(paper)

    def _check_owners(self, user_ids: list[int]) -> None:
        if not self.env.user.has_group("base.group_system") and any(user_id != self.env.uid for user_id in user_ids):
            raise AccessError(self.env._("You can change only your own printers."))

    @api.model_create_multi
    def create(self, vals_list: list[dict]) -> "odoo.model.printnode_preference":
        self._check_owners([values.get("user_id", self.env.uid) for values in vals_list])
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
            "domain": [("user_id", "=", self.env.uid)],
            "context": {"default_user_id": self.env.uid},
        }


class PrintNodeRoutingActor(models.AbstractModel):
    _name = "printnode.routing"
    _description = "Printer routing"

    def _check_actor(self) -> None:
        if self.env.uid == SUPERUSER_ID or not self.env.user._is_internal() or self.env.context.get("cron_id"):
            raise AccessError(self.env._("Printing needs the signed-in person. Open My printers in your own account."))
