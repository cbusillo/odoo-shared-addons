import json
from urllib.parse import parse_qs, unquote_plus, urlsplit

from lxml import html
from odoo.tests import HttpCase, tagged


@tagged("post_install", "-at_install")
class TestStaffEntry(HttpCase):
    def test_staff_entry_selects_only_configured_provider(self) -> None:
        self.env["authentik.sso.config"].apply_from_values(
            {"provider_name": "Staff SSO", "client_id": "staff", "base_url": "https://id.example.invalid"}
        )
        self.env["auth.oauth.provider"].create(
            {
                "name": "Another provider",
                "enabled": True,
                "client_id": "other",
                "auth_endpoint": "https://other.example.invalid/authorize",
                "validation_endpoint": "https://other.example.invalid/userinfo",
                "body": "Another account",
            }
        )
        parameters = self.env["ir.config_parameter"]
        parameters.set_bool("authentik_sso.staff_login_only", False)
        self.assertTrue(html.fromstring(self.url_open("/odoo").content).xpath("//input[@name='password']"))
        parameters.set_bool("authentik_sso.staff_login_only", True)
        for route in ("/odoo", "/odoo/contacts?view=list", "/web", "/web/", "/scoped_app/calendar"):
            with self.subTest(route=route):
                entry = self.url_open(route, allow_redirects=False)
                login = self.url_open(entry.headers["Location"], allow_redirects=False)
                self.assertEqual(login.status_code, 303)
                provider = urlsplit(login.headers["Location"])
                self.assertEqual(provider.hostname, "id.example.invalid")
                query = parse_qs(provider.query)
                self.assertEqual(query["client_id"], ["staff"])
                state = json.loads(query["state"][0])
                self.assertEqual(unquote_plus(state["r"]).rstrip("?"), self.base_url() + route)

        for destination in ("/odoo", "/scoped_app/calendar"):
            with self.subTest(logout=destination):
                self.authenticate("admin", "admin")
                logout = self.url_open("/web/session/logout", data={"csrf_token": self.csrf_token(), "redirect": destination})
                signed_out = html.fromstring(logout.content)
                self.assertTrue(signed_out.xpath("//*[@role='status' and normalize-space()]"))
                self.assertFalse(signed_out.xpath("//input[@name='password']"))
                (retry_link,) = signed_out.xpath("//a[contains(@href, 'id.example.invalid')]/@href")
                retry_state = json.loads(parse_qs(urlsplit(retry_link).query)["state"][0])
                self.assertEqual(unquote_plus(retry_state["r"]), self.base_url() + destination)

        error_page = html.fromstring(self.url_open("/web/login?redirect=/odoo&oauth_error=2").content)
        self.assertTrue(error_page.xpath("//*[@role='alert' and normalize-space()]"))
        self.assertTrue(error_page.xpath("//a[contains(@href, 'id.example.invalid')]"))
        self.assertFalse(error_page.xpath("//input[@name='password'] | //a[contains(@href, 'other.example.invalid')]"))

        for url in ("/web/login", "/web/login?redirect=/my", "/web/login?redirect=/shop", "/web/login?redirect=/odoo&token=fixture"):
            with self.subTest(url=url):
                document = html.fromstring(self.url_open(url).content)
                self.assertTrue(document.xpath("//input[@name='password']"))
                self.assertTrue(document.xpath("//a[contains(@href, 'other.example.invalid')]"))

        self.env["auth.oauth.provider"].search([("name", "=", "Staff SSO")]).enabled = False
        staff = html.fromstring(self.url_open("/odoo").content)
        self.assertTrue(staff.xpath("//*[@role='alert' and normalize-space()]"))
        self.assertFalse(staff.xpath("//input[@name='password'] | //a[contains(@href, 'other.example.invalid')]"))
