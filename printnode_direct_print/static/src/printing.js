import { usePlugin } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { _t } from "@web/core/l10n/translation";
import { useService } from "@web/core/utils/hooks";
import { ORM } from "@web/core/orm_plugin";

export async function routeReport(action, orm) {
    if (!action.printnode_direct || action.report_type !== "qweb-pdf") {
        return false;
    }
    await orm.call("ir.actions.report", "printnode_print", [[action.id]], {
        res_ids:
            action.data && Object.keys(action.data).length
                ? null
                : action.context?.active_ids || [],
        data: action.data || null,
        context: action.context || {},
    });
    return true;
}

export function printReport(action) {
    return routeReport(action, usePlugin(ORM));
}

export function myPrintersItem() {
    const orm = usePlugin(ORM);
    const action = useService("action");
    return {
        type: "item",
        id: "my_printers",
        description: _t("My printers"),
        sequence: 55,
        callback: async () => {
            const description = await orm.call("printnode.preference", "action_my_printers", []);
            await action.doAction(description);
        },
    };
}

registry.category("ir.actions.report handlers").add("printnode_direct_print", printReport);
registry.category("user_menuitems").add("printnode_my_printers", myPrintersItem);
