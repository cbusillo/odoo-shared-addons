from odoo import api, fields, models


class ResDeviceLog(models.Model):
    _inherit = "res.device.log"

    user_agent = fields.Char(required=False)
    platform = fields.Char(readonly=True)
    browser = fields.Char(readonly=True)
    device_type = fields.Selection([("computer", "Computer"), ("mobile", "Mobile")], readonly=True)
    legacy_user_agent_unavailable = fields.Boolean(readonly=True, copy=False, default=False)

    _user_agent_present = models.Constraint(
        "CHECK (user_agent IS NOT NULL OR legacy_user_agent_unavailable IS TRUE)",
        "New device logs require the request's raw User-Agent.",
    )


class ResDevice(models.Model):
    _inherit = "res.device"

    raw_user_agent_unavailable = fields.Boolean("Raw User-Agent unavailable", compute="_compute_raw_user_agent_unavailable")

    @api.depends("user_agent")
    def _compute_raw_user_agent_unavailable(self) -> None:
        for device in self:
            device.raw_user_agent_unavailable = device.user_agent is False

    def _historical_device(self) -> "odoo.model.res_device":
        self.ensure_one()
        return self

    @api.depends("user_agent")
    def _compute_device_info(self) -> None:
        native = self.filtered(lambda device: device.user_agent is not False)
        super(ResDevice, native)._compute_device_info()
        historical = self - native
        logs = self.env["res.device.log"].browse([device._historical_device().id for device in historical])
        for device, log in zip(historical, logs, strict=True):
            device.platform = log.platform or self.env._("Unknown")
            device.browser = log.browser or self.env._("Unknown")
            device.device_type = log.device_type or self.env._("Unknown")
            device.browser_version = self.env._("Unknown")
            device.browser_language = self.env._("Unknown")


class ResSession(models.Model):
    _inherit = "res.session"

    def _historical_device(self) -> "odoo.model.res_device":
        self.ensure_one()
        devices = self.device_ids.sorted("last_activity", reverse=True)
        current = devices.filtered("is_current") if self.is_current else self.env["res.device"]
        return current or devices[:1]
