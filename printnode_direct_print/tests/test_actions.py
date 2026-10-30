from odoo import Command
from odoo.tests import HttpCase, tagged


@tagged("post_install", "-at_install")
class TestPersonalPrintersAction(HttpCase):
    def test_user_menu_opens_empty_personal_list_and_new_preference(self) -> None:
        person = (
            self.env["res.users"]
            .with_context(no_reset_password=True)
            .create(
                {
                    "name": "Printer menu fixture",
                    "login": "printer-menu-fixture",
                    "group_ids": [Command.set([self.env.ref("base.group_user").id])],
                }
            )
        )
        self.browser_js(
            "/odoo",
            """
            (async () => {
                async function waitFor(selector) {
                    for (let attempt = 0; attempt < 300; attempt++) {
                        const element = document.querySelector(selector);
                        if (element) {
                            return element;
                        }
                        await new Promise((resolve) => setTimeout(resolve, 100));
                    }
                    throw new Error(`Missing ${selector}`);
                }
                (await waitFor(".o_user_menu button.dropdown-toggle")).click();
                (await waitFor('[data-menu="my_printers"]')).click();
                await waitFor(".o_list_view");
                if (document.querySelector(".o_data_row")) {
                    throw new Error("A new user's personal printers must start empty");
                }
                await waitFor('.o_list_view button[name="%(discover_printers)d"]');
                (await waitFor(".o_list_button_add")).click();
                await waitFor('.o_form_view .o_field_widget[name="paperformat_id"]');
                await waitFor('.o_form_view .o_field_widget[name="printer_id"]');
                console.log("test successful");
            })();
            """.replace("%(discover_printers)d", str(self.env.ref("printnode_direct_print.discover_printers").id)),
            login=person.login,
            timeout=120,
        )
