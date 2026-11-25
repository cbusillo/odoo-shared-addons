import { registry } from "@web/core/registry";
import { patch } from "@web/core/utils/patch";
import { websiteService } from "@website/services/website_service";
import "@website/services/website_custom_menus";
import { user } from "@web/core/user";

const access = (website) => website.pageDocument?.documentElement.dataset.siteEditorAccess;

patch(websiteService, {
    async start(...args) {
        const website = await super.start(...args);
        if (await user.hasGroup("website_site_editor.group_editor") && !(await user.hasGroup("base.group_system"))) {
            patch(website, {
                get isRestrictedEditor() {
                    return super.isRestrictedEditor && access(this) === "assigned";
                },
                get currentWebsite() {
                    const current = super.currentWebsite;
                    if (current?.metadata) {
                        const allowed = access(this) === "assigned";
                        current.metadata.editable = allowed && !!this.pageDocument.querySelector("[data-site-editor-body]");
                        current.metadata.translatable = false;
                        current.metadata.canPublish = false;
                        current.metadata.canOptimizeSeo = false;
                        current.metadata.editableInBackend = false;
                    }
                    return current;
                },
            });
        }
        return website;
    },
});

const menus = registry.category("website_custom_menus");
patch(menus.get("website.menu_edit_menu"), {
    isDisplayed(env) {
        return access(env.services.website) === "assigned" || super.isDisplayed(env);
    },
});
patch(menus.get("website.menu_ace_editor"), {
    isDisplayed(env) {
        return !access(env.services.website) && super.isDisplayed(env);
    },
});
