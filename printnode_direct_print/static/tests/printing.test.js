import { describe, expect, test } from "@odoo/hoot";
import { myPrintersItem, routeReport } from "@printnode_direct_print/printing";
import { registry } from "@web/core/registry";
import {
    clearRegistry,
    contains,
    getService,
    defineModels,
    fields,
    models,
    serverState,
    webModels,
    mountWithCleanup,
    onRpc,
} from "@web/../tests/web_test_helpers";
import { WebClient } from "@web/webclient/webclient";

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
            expect(kwargs.res_ids).toBe(null);
            expect(kwargs.data).toEqual(action.data);
            expect.step("prepared");
            return { state: "prepared", printer: "Receiving" };
        },
    };
    expect(await routeReport(action, orm)).toBe(true);
    expect.verifySteps(["prepared"]);
});

test("printing failures propagate without success or download fallback", async () => {
    const orm = {
        call: async () => {
            throw new Error("fixture offline");
        },
    };
    await expect(
        routeReport({ id: 42, report_type: "qweb-pdf", printnode_direct: true }, orm)
    ).rejects.toThrow();
});

test("the native action path prints and preserves close callbacks", async () => {
    onRpc("printnode_print", ({ kwargs }) => {
        expect(kwargs.res_ids).toBe(null);
        expect(kwargs.data).toEqual({ form: { quantity: 2 } });
        expect.step("prepared");
        return { state: "prepared", printer: "Receiving" };
    });
    await mountWithCleanup(WebClient);
    const action = {
        id: 42,
        type: "ir.actions.report",
        name: "Fixture report",
        report_name: "fixture",
        report_type: "qweb-pdf",
        printnode_direct: true,
        context: { active_ids: [17] },
        data: { form: { quantity: 2 } },
    };
    for (const close of [false, true]) {
        await getService("action").doAction(
            { ...action, close_on_report_download: close },
            { onClose: () => expect.step("closed") }
        );
    }
    expect.verifySteps(["prepared", "closed", "prepared", "closed"]);
});

describe("personal printer menu", () => {
    describe.current.tags("desktop");

    class PrintNodePreference extends models.Model {
        _name = "printnode.preference";

        user_id = fields.Many2one({ relation: "res.users" });
        size_label = fields.Char();
        printer_id = fields.Char();
        _views = {
            list: '<list><field name="size_label"/><field name="printer_id"/></list>',
            form: '<form><field name="user_id"/><field name="printer_id"/></form>',
            search: "<search/>",
        };
    }

    defineModels([PrintNodePreference, webModels.ResUsers]);

    for (const empty of [false, true]) {
        test(`opens personal printers through the native action service (empty=${empty})`, async () => {
            PrintNodePreference._records = empty
                ? []
                : [
                      { id: 1, user_id: serverState.userId, size_label: "Letter", printer_id: "Desk" },
                      { id: 2, user_id: serverState.userId + 1, size_label: "Label", printer_id: "Other" },
                  ];
            const menus = registry.category("user_menuitems");
            clearRegistry(menus);
            menus.add("my_printers", myPrintersItem);
            onRpc("action_my_printers", () => ({
                type: "ir.actions.act_window",
                name: "My printers",
                res_model: "printnode.preference",
                view_mode: "list,form",
                views: [[false, "list"], [false, "form"]],
                domain: [["user_id", "=", serverState.userId]],
                context: { default_user_id: serverState.userId },
            }));
            onRpc("default_get", ({ kwargs }) => {
                expect(kwargs.context.default_user_id).toBe(serverState.userId);
                expect.step("current user default");
            });
            await mountWithCleanup(WebClient);
            await contains(".o_user_menu button.dropdown-toggle").click();
            await contains('[data-menu="my_printers"]').click();
            expect(".o_list_view").toHaveCount(1);
            expect(".o_data_row").toHaveCount(empty ? 0 : 1);
            if (!empty) {
                expect(".o_data_row").toHaveText(/Desk/);
            }
            await contains(".o_list_button_add").click();
            expect(".o_form_view").toHaveCount(1);
            expect.verifySteps(["current user default"]);
        });
    }
});
