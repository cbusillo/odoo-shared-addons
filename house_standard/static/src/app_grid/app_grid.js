import { Component } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

export class AppGrid extends Component {
    static template = "house_standard.AppGrid";
    static props = ["*"];

    setup() {
        this.appMenuService = useService("app_menu");
    }

    get apps() {
        return this.appMenuService.getAppsMenuItems();
    }

    openApp(app) {
        this.appMenuService.selectApp(app);
    }
}

registry.category("actions").add("house_standard.app_grid", AppGrid);
