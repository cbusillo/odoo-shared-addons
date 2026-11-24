import json

from odoo.tests import HttpCase, tagged
from odoo.tests.common import DEFAULT_SUCCESS_SIGNAL, new_test_user

WAIT_FOR_JS = """
    async function waitFor(find, description) {
        const deadline = Date.now() + 20000;
        while (Date.now() < deadline) {
            const result = find();
            if (result) return result;
            await new Promise((resolve) => setTimeout(resolve, 100));
        }
        throw new Error(description);
    }
"""


@tagged("-at_install", "post_install")
class TestAppGridBrowser(HttpCase):
    def test_apps_button_from_a_record_returns_to_the_login_grid(self) -> None:
        staff = new_test_user(self.env, login="house-grid-staff", groups="base.group_user,base.group_partner_manager")
        contact = self.env["res.partner"].create({"name": "Synthetic Home Contact"})
        self.browser_js(
            "/odoo",
            f"""(async () => {{
                {WAIT_FOR_JS}
                const tileSelector = ".o_house_app_grid .o_house_app";
                const appIds = () => Array.from(
                    document.querySelectorAll(tileSelector), (app) => app.dataset.menuXmlid
                ).join(",");
                const initialApps = appIds();
                const homePath = location.pathname;
                const isHome = () => location.pathname === homePath && appIds() === initialApps &&
                    document.querySelector(".mk_apps_sidebar .nav-link")?.getClientRects().length &&
                    !document.querySelector(".mk_app_menu, .o_menu_brand");
                document.querySelector(`${{tileSelector}}[data-menu-xmlid="contacts.menu_contacts"]`).click();
                const card = await waitFor(
                    () => Array.from(document.querySelectorAll(".o_kanban_record")).find(
                        (item) => item.textContent.includes({json.dumps(contact.name)})
                    ),
                    "The Contacts tile did not open the synthetic contact's app"
                );
                card.click();
                await waitFor(() => document.querySelector(".o_form_view"), "The contact form did not open");
                const recordPath = location.pathname;
                document.querySelector('.o_navbar_apps_menu [data-hotkey="h"]').click();
                await waitFor(isHome, "The apps button did not return from the contact to the login grid");
                history.back();
                await waitFor(
                    () => document.querySelector(".o_form_view") && location.pathname === recordPath,
                    "Browser Back did not return to the contact"
                );
                history.forward();
                await waitFor(isHome, "Browser Forward did not restore Home without the contact app's navbar");
                console.log({json.dumps(DEFAULT_SUCCESS_SIGNAL)});
            }})()""",
            ready="Boolean(document.querySelector('.o_house_app_grid .o_house_app'))",
            login=staff.login,
        )

    def test_explicit_home_action_still_opens_on_login(self) -> None:
        action = self.env.ref("contacts.action_contacts")
        staff = new_test_user(
            self.env,
            login="house-chosen-home",
            groups="base.group_user,base.group_partner_manager",
            action_id=action.id,
        )
        action_path = action.path or f"action-{action.id}"
        self.browser_js(
            "/odoo",
            f"console.log({json.dumps(DEFAULT_SUCCESS_SIGNAL)});",
            ready=f"location.pathname === {json.dumps(f'/odoo/{action_path}')}",
            login=staff.login,
        )

    def test_mobile_home_menu_lists_apps_on_the_first_tap(self) -> None:
        self.browser_size = "390x844"
        staff = new_test_user(self.env, login="house-mobile-staff", groups="base.group_user,base.group_partner_manager")
        self.browser_js(
            "/odoo",
            f"""(async () => {{
                {WAIT_FOR_JS}
                const homePath = location.pathname;
                document.querySelector(".o_menu_toggle").click();
                const contacts = await waitFor(
                    () => document.querySelector('.o_app_menu_sidebar .o_app[data-menu-xmlid="contacts.menu_contacts"]'),
                    "The first tap from Home did not show Contacts in the mobile menu"
                );
                contacts.click();
                await waitFor(
                    () => location.pathname !== homePath && !document.querySelector(".o_house_app_grid, .o_app_menu_sidebar"),
                    "The Contacts entry did not open the app and close the drawer"
                );
                console.log({json.dumps(DEFAULT_SUCCESS_SIGNAL)});
            }})()""",
            ready="Boolean(document.querySelector('.o_house_app_grid .o_house_app'))",
            login=staff.login,
        )

    def test_mobile_all_apps_opens_home_from_the_record_menu(self) -> None:
        self.browser_size = "390x844"
        contact = self.env["res.partner"].create({"name": "Synthetic Mobile Home Contact"})
        contact_action = self.env.ref("contacts.action_contacts")
        self.browser_js(
            f"/odoo/action-{contact_action.id}/{contact.id}",
            f"""(async () => {{
                {WAIT_FOR_JS}
                document.querySelector(".o_menu_toggle").click();
                const allApps = await waitFor(
                    () => document.querySelector(".o_app_menu_sidebar .o_sidebar_topbar a"),
                    "The contextual mobile menu did not open"
                );
                const drawer = allApps.closest(".o_app_menu_sidebar");
                const sections = drawer.querySelectorAll(
                    '.o_burger_menu_content li[data-menu-xmlid^="contacts."]:not(.o_app)'
                );
                if (drawer.querySelector(".o_app") || ![...sections].some((section) => section.getClientRects().length)) {{
                    throw new Error("The contact record's menu did not show Contacts sections");
                }}
                allApps.click();
                await waitFor(
                    () => document.querySelector(".o_house_app_grid .o_house_app") &&
                          !document.querySelector(".o_app_menu_sidebar"),
                    "All Apps did not close the drawer and open the Home grid"
                );
                document.querySelector(".o_menu_toggle").click();
                await waitFor(
                    () => document.querySelector('.o_app_menu_sidebar .o_app[data-menu-xmlid="contacts.menu_contacts"]'),
                    "Returning to Home from a record kept the drawer in the previous app"
                );
                console.log({json.dumps(DEFAULT_SUCCESS_SIGNAL)});
            }})()""",
            ready="Boolean(document.querySelector('.o_form_view .o_field_widget[name=name]'))",
            login="admin",
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
                const odooEndpoint = {json.dumps(self.env.ref("auth_oauth.provider_openerp").auth_endpoint)};
                if ([...document.querySelectorAll('a[href]')].some((link) => link.href.startsWith(odooEndpoint))) {{
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
