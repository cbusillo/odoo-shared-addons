import os
import re
from urllib.parse import urlsplit

from odoo import fields, models


class Website(models.Model):
    _inherit = "website"

    consent_first_ga4 = fields.Boolean(string="Use consent-first GA4", copy=False)

    def _consent_ga4_config(self) -> dict[str, str]:
        self.ensure_one()
        if not self.consent_first_ga4:
            return {}
        if os.environ.get("PLATFORM_INSTANCE", "").strip().lower() not in {"prod", "production"}:
            return {"mode": "preview"}
        if not (
            self.cookies_bar and self.block_third_party_domains and re.fullmatch(r"G-[A-Z0-9]+", self.google_analytics_key or "")
        ):
            return {}
        domain = self.domain or ""
        try:
            origin = urlsplit(domain)
            valid_origin = (
                origin.scheme == "https"
                and origin.hostname
                and origin.username is None
                and origin.path in {"", "/"}
                and origin.port != 0
                and domain.rstrip("/") == f"https://{origin.netloc}"
                and not re.search(r"[\s\\]", domain)
            )
        except ValueError:
            return {}
        if not valid_origin:
            return {}
        return {"mode": "production", "origin": f"https://{origin.netloc}", "measurementId": self.google_analytics_key}
