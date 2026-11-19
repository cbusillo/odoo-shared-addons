import { Component } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { session } from "@web/session";

class EnvironmentBanner extends Component {
    static template = "environment_banner.EnvironmentBanner";
}

if (session.show_environment_banner !== false) {
    registry.category("main_components").add("environment_banner", { Component: EnvironmentBanner });
}
