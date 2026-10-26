from odoo.tests import HttpCase, tagged


@tagged("-at_install", "post_install")
class TestEnvironmentBannerBrowser(HttpCase):
    def test_banner_follows_instance_setting(self) -> None:
        parameters = self.env["ir.config_parameter"].sudo()
        parameters.set_str("environment_banner.production_hostnames", "")
        for enabled in (True, False):
            with self.subTest(enabled=enabled):
                parameters.set_str("environment_banner.enabled", str(enabled))
                self.browser_js(
                    "/odoo",
                    f"""
                    (async () => {{
                    await new Promise(requestAnimationFrame);
                    await new Promise(requestAnimationFrame);
                    const banner = document.querySelector('.environment-banner');
                    if (Boolean(banner) !== {str(enabled).lower()}) {{
                        throw new Error('Environment banner does not match instance setting');
                    }}
                    if (banner && !banner.classList.contains('environment-localhost')) {{
                        throw new Error('Environment banner does not identify the local test instance');
                    }}
                    console.log('test successful');
                    }})();
                    """,
                    ready="Boolean(document.querySelector('.o_main_navbar'))",
                    login="admin",
                    timeout=60,
                )
