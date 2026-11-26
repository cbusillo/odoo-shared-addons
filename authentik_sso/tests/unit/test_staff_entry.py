from urllib.parse import parse_qs, urlsplit

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
        for route in ("/odoo", "/odoo/contacts?view=list", "/web", "/scoped_app/calendar"):
            with self.subTest(route=route):
                page = self.url_open(route)
                destination = parse_qs(urlsplit(page.url).query)["redirect"][0]
                self.assertEqual(destination.rstrip("?"), route)
                document = html.fromstring(page.content)
                self.assertFalse(document.xpath("//input[@name='password'] | //owl-component[@name='web.user_switch']"))
                self.assertFalse(document.xpath("//a[contains(@href, 'other.example.invalid')]"))
                (link,) = document.xpath("//a[contains(@href, 'id.example.invalid')]/@href")
                self.assertEqual(parse_qs(urlsplit(link).query)["client_id"], ["staff"])

        for url in ("/web/login", "/web/login?redirect=/my", "/web/login?redirect=/shop", "/web/login?redirect=/odoo&token=fixture"):
            with self.subTest(url=url):
                document = html.fromstring(self.url_open(url).content)
                self.assertTrue(document.xpath("//input[@name='password']"))
                self.assertTrue(document.xpath("//a[contains(@href, 'other.example.invalid')]"))

        self.env["auth.oauth.provider"].search([("name", "=", "Staff SSO")]).enabled = False
        staff = html.fromstring(self.url_open("/odoo").content)
        self.assertTrue(staff.xpath("//*[@role='alert' and normalize-space()]"))
        self.assertFalse(staff.xpath("//input[@name='password'] | //a[contains(@href, 'other.example.invalid')]"))
