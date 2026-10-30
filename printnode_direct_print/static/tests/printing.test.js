import { expect, test } from "@odoo/hoot";
import { routeReport } from "@printnode_direct_print/printing";
import {
    getService,
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
