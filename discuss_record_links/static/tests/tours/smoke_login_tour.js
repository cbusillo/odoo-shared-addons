/** @odoo-module */

import { registry } from "@web/core/registry";

const appsControl = ".o_navbar_apps_menu [data-hotkey='h']";

registry.category("web_tour.tours").add("smoke_login_tour", {
    url: "/web",
    steps: () => [
        {
            content: "Load the web client shell",
            trigger: ".o_web_client",
        },
        {
            content: "Open the apps menu",
            trigger: `${appsControl}, .o_home_menu`,
            run(actions) {
                const control = document.querySelector(appsControl);
                if (control) {
                    actions.click(control);
                }
            },
        },
        {
            content: "Ensure the apps menu is visible",
            trigger: ".o_app[data-menu-xmlid], .o_house_app[data-menu-xmlid]",
        },
        {
            content: "Confirm the user menu renders",
            trigger: ".o_user_menu",
        },
    ],
});
