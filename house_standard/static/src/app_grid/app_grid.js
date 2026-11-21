import { Component } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { patch } from "@web/core/utils/patch";
import { WebClient } from "@web/webclient/webclient";

const HOME_ACTION_TAG = "house_standard.app_grid";

export class AppGrid extends Component {
    static template = "house_standard.AppGrid";

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

registry.category("actions").add(HOME_ACTION_TAG, AppGrid);

patch(WebClient.prototype, {
    async loadRouterState() {
        await super.loadRouterState();
        if (this.actionService.currentController?.action.tag === HOME_ACTION_TAG) {
            this.menuService.setCurrentMenu({ appID: null });
        }
    },
});
