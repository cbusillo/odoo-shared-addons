import json

from odoo.tests import HttpCase, tagged
from odoo.tests.common import DEFAULT_SUCCESS_SIGNAL

OPEN_FIRST_APP_JS = f"""(async () => {{
    const app = document.querySelector('.o_house_app');
    const name = app.textContent.trim();
    app.click();
    const deadline = Date.now() + 20000;
    while (document.querySelector('.o_menu_brand')?.textContent.trim() !== name) {{
        if (Date.now() > deadline) {{
            throw new Error(`The ${{name}} app did not open from the app grid`);
        }}
        await new Promise((resolve) => setTimeout(resolve, 100));
    }}
    console.log({json.dumps(DEFAULT_SUCCESS_SIGNAL)});
}})()"""


@tagged("-at_install", "post_install")
class TestAppGridBrowser(HttpCase):
    def test_web_client_lands_on_app_grid_and_opens_an_app(self) -> None:
        self.browser_js(
            "/odoo", OPEN_FIRST_APP_JS, ready="Boolean(document.querySelector('.o_house_app_grid .o_house_app'))", login="admin"
        )


@tagged("-at_install", "post_install")
class TestHouseLoginBrowser(HttpCase):
    def test_login_keeps_sso_and_passkeys_without_public_signup(self) -> None:
        self.env["auth.oauth.provider"].create(
            {
                "name": "Authentik",
                "auth_endpoint": "https://auth.example.test/authorize",
                "client_id": "house-login-test",
                "validation_endpoint": "https://auth.example.test/userinfo",
                "body": "Sign in with Authentik",
                "css_class": "house_authentik_test_provider",
                "enabled": True,
            }
        )
        self.assertEqual(self.url_open("/web/signup").status_code, 404)
        self.browser_js(
            "/web/login",
            f"""(async () => {{
                if (document.querySelector('a[href*="/web/signup"]')) {{
                    throw new Error("Public signup link is still offered");
                }}
                if (document.querySelector('.o_odoo_provider')) {{
                    throw new Error("Odoo.com sign-in is still offered");
                }}
                if (!document.querySelector('.house_authentik_test_provider')) {{
                    throw new Error("Authentik sign-in is missing");
                }}
                if (!document.querySelector('.passkey_login_link')) {{
                    throw new Error("Passkey sign-in is missing");
                }}
                const data = new URLSearchParams({{
                    csrf_token: document.querySelector('input[name="csrf_token"]').value,
                    name: "Uninvited Browser",
                    login: "house-uninvited-browser@example.test",
                    password: "synthetic-signup-password",
                    confirm_password: "synthetic-signup-password",
                }});
                const response = await fetch('/web/signup', {{method: 'POST', body: data}});
                if (response.status !== 404) {{
                    throw new Error(`Uninvited signup returned ${{response.status}} instead of 404`);
                }}
                console.log({json.dumps(DEFAULT_SUCCESS_SIGNAL)});
            }})()""",
            ready="Boolean(document.querySelector('.oe_login_form'))",
        )
        self.assertFalse(self.env["res.users"].search([("login", "=", "house-uninvited-browser@example.test")]))
