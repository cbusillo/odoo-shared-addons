import { describe, expect, test } from "@odoo/hoot";
import { myPrintersItem, routeReport } from "@printnode_direct_print/printing";
import { registry } from "@web/core/registry";
import { clearRegistry, contains, mockService, mountWithCleanup, onRpc } from "@web/../tests/web_test_helpers";
import { UserMenu } from "@web/webclient/user_menu/user_menu";

test("ordinary reports keep the native download path", async () => {
    expect(await routeReport({ report_type: "qweb-pdf" }, {})).toBe(false);
});

test("direct reports preserve wizard data and selected records without choosing a printer", async () => {
    const action = {
        id: 42,
        report_type: "qweb-pdf",
        printnode_direct: true,
        data: { form: { quantity: 2 } },
        context: { active_ids: [17], allowed_company_ids: [1] },
        close_on_report_download: true,
    };
    const orm = {
        async call(model, method, args, kwargs) {
            expect(model).toBe("ir.actions.report");
            expect(method).toBe("printnode_print");
            expect(args).toEqual([[action.id]]);
            expect(kwargs).toEqual({ res_ids: [17], data: action.data, context: action.context });
            expect.step("prepared");
            return { state: "prepared", printer: "Receiving" };
        },
    };
    expect(await routeReport(action, orm)).toBe(true);
    expect.verifySteps(["prepared"]);
});

test("printing failures propagate without success or download fallback", async () => {
    const orm = { call: async () => { throw new Error("fixture offline"); } };
    await expect(routeReport({ id: 42, report_type: "qweb-pdf", printnode_direct: true }, orm)).rejects.toThrow();
});

describe("personal printer menu", () => {
    describe.current.tags("desktop");

    test("opens the server-owned personal settings from the real user menu", async () => {
        const menus = registry.category("user_menuitems");
        clearRegistry(menus);
        menus.add("my_printers", myPrintersItem);
        const personalAction = { type: "ir.actions.act_window", res_model: "printnode.preference" };
        onRpc("action_my_printers", () => {
            expect.step("personal settings");
            return personalAction;
        });
        mockService("action", {
            async doAction(action) {
                expect(action).toEqual(personalAction);
                expect.step("opened");
            },
        });
        await mountWithCleanup(UserMenu);
        await contains("button.dropdown-toggle").click();
        await contains('[data-menu="my_printers"]').click();
        expect.verifySteps(["personal settings", "opened"]);
    });
});
