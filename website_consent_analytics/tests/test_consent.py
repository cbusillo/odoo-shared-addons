import json
import os
from pathlib import Path
from unittest.mock import patch
from urllib.parse import urlsplit

from lxml import html
from odoo.tests import HttpCase, tagged


@tagged("post_install", "-at_install")
class TestWebsiteConsent(HttpCase):
    def setUp(self) -> None:
        super().setUp()
        self.site = self.env.ref("base.default_website")
        self.site.write(
            {
                "domain": self.base_url().replace("http:", "https:"),
                "cookies_bar": True,
                "block_third_party_domains": True,
                "google_analytics_key": "G-FIXTURE123",
                "consent_first_ga4": True,
            }
        )
        self.tag_requests: list[str] = []

    def fetch_proxy(self, url: str) -> dict:
        host = urlsplit(url).hostname or ""
        if host == "www.googletagmanager.com" or host == "google-analytics.com" or host.endswith(".google-analytics.com"):
            self.tag_requests.append(url)
            return self.make_fetch_proxy_response("window.fixtureTagLoads = (window.fixtureTagLoads || 0) + 1;")
        return super().fetch_proxy(url)

    def test_site_selection_and_copied_settings(self) -> None:
        other = self.env["website"].create(
            {
                "name": "Ordinary site",
                "domain": "https://ordinary.example.invalid",
                "google_analytics_key": "G-OTHER123",
            }
        )
        with patch.dict(os.environ, PLATFORM_INSTANCE="production"):
            response = self.url_open("/", headers={"Host": "ordinary.example.invalid"})
            self.assertEqual(response.status_code, 200)
            page = html.fromstring(response.content)
            self.assertTrue(page.xpath("//script[@id='tracking_code_config']"))
            self.assertIn(other.google_analytics_key, response.text)
            self.assertFalse(page.xpath("//meta[@name='consent-first-ga4']"))
        for lane in ("testing", "preview", "unexpected", ""):
            with self.subTest(lane=lane), patch.dict(os.environ, PLATFORM_INSTANCE=lane):
                response = self.url_open("/cookie-policy")
                self.assertEqual(response.status_code, 200)
                self.assertNotIn(self.site.google_analytics_key, response.text)
                page = html.fromstring(response.content)
                self.assertFalse(page.xpath("//script[@id='tracking_code' or @id='tracking_code_config']"))
                self.assertEqual(json.loads(page.xpath("//meta[@name='consent-first-ga4']/@content")[0]), {"mode": "preview"})

    def test_ineligible_production_settings(self) -> None:
        with patch.dict(os.environ, PLATFORM_INSTANCE="prod"):
            for field, value in (
                ("cookies_bar", False),
                ("block_third_party_domains", False),
                ("google_analytics_key", False),
                ("google_analytics_key", "GTM-FIXTURE"),
                ("domain", "http://public.example.invalid"),
            ):
                with self.subTest(field=field, value=value):
                    previous = self.site[field]
                    self.site[field] = value
                    self.assertFalse(self.site._consent_ga4_config())
                    self.site[field] = previous

    def test_native_choices_and_local_preview(self) -> None:
        fixture = Path(__file__).with_name("browser.js").read_text()
        for lane in ("production", "testing"):
            with self.subTest(lane=lane), patch.dict(os.environ, PLATFORM_INSTANCE=lane):
                self.tag_requests.clear()
                self.browser_js(
                    "/?private=never-send#fragment",
                    f"const local = {json.dumps(lane == 'testing')};\n{fixture}",
                    ready="document.body?.getAttribute('is-ready') === 'true' && !!document.querySelector('.o_cookies_bar_toggle')",
                )
                expected = (
                    [] if lane == "testing" else [f"https://www.googletagmanager.com/gtag/js?id={self.site.google_analytics_key}"]
                )
                self.assertEqual(self.tag_requests, expected)

    def test_first_visit_and_saved_choices(self) -> None:
        with patch.dict(os.environ, PLATFORM_INSTANCE="production"):
            for choice, accepted in ((None, False), ("broken", False), ('{"optional":"true"}', False), ('{"optional":true}', True)):
                with self.subTest(choice=choice):
                    self.tag_requests.clear()
                    self.browser_js(
                        "/cookie-policy",
                        f"""
                        const {{ startConsentAnalytics }} = odoo.loader.modules.get("@website_consent_analytics/analytics");
                        if ({json.dumps(choice)} !== null) {{
                            document.cookie = "website_cookies_bar=" + encodeURIComponent({json.dumps(choice)}) + "; path=/";
                        }}
                        startConsentAnalytics({{ pages: new Map([["/cookie-policy", {{ path: "/", title: "Home" }}]]) }});
                        const events = Array.from(window.dataLayer || []).filter(([kind]) => kind === "event");
                        if (events.length !== {int(accepted)} || !!window.dataLayer !== {json.dumps(accepted)}) {{
                            throw Error("Unexpected initial collection");
                        }}
                        if ({json.dumps(accepted)}) {{
                            document.querySelector('script[src*="googletagmanager.com"]').addEventListener("load",
                                () => console.log("test successful"), {{ once: true }});
                        }} else {{
                            console.log("test successful");
                        }}
                        """,
                        ready="document.body?.getAttribute('is-ready') === 'true'",
                    )
                    self.assertEqual(len(self.tag_requests), int(accepted))
