import os
from unittest.mock import patch

from odoo.tests import HttpCase, tagged


@tagged("-at_install", "post_install")
class TestEnvironmentBannerBrowser(HttpCase):
    def test_only_production_hides_the_warning(self) -> None:
        for lane, shown in (("preview", True), ("testing", True), ("unknown", True), ("", True), ("prod", False)):
            with self.subTest(lane=lane), patch.dict(os.environ, {"PLATFORM_INSTANCE": lane}):
                self.browser_js(
                    "/odoo",
                    f"""
                    (async () => {{
                        await new Promise(requestAnimationFrame);
                        const banner = document.querySelector(".environment-banner");
                        if (Boolean(banner) !== {str(shown).lower()}) {{
                            throw new Error("Environment banner visibility is incorrect");
                        }}
                        if (banner && !banner.textContent.includes("This is not production. Data you enter here can be lost.")) {{
                            throw new Error("Environment banner is missing the data loss warning");
                        }}
                        if (banner) {{
                            const bounds = banner.getBoundingClientRect();
                            if (!banner.checkVisibility() || bounds.height === 0 || bounds.top < 0 ||
                                bounds.bottom > window.innerHeight) {{
                                throw new Error("The banner is outside the visible page");
                            }}
                        }}
                        console.log("test successful");
                    }})();
                    """,
                    ready="Boolean(document.querySelector('.o_main_navbar'))",
                    login="admin",
                )
