from odoo import models


class PublisherWarrantyContract(models.AbstractModel):
    _inherit = "publisher_warranty.contract"

    def update_notification(self, cron_mode: bool = True) -> bool:
        _ = cron_mode
        return True
