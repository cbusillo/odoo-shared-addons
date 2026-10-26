import { defineMailModels } from "@mail/../tests/mail_test_helpers";
import { describe, expect, test } from "@odoo/hoot";
import { destroyApp, makeTestApp, mountWebClient } from "@web/../tests/web_test_helpers";
import { browser } from "@web/core/browser/browser";
import { patch } from "@web/core/utils/patch";
import { WebClient } from "@web/webclient/webclient";

import "@notification_permission_patch/js/notification_permission_patch";

defineMailModels();

describe("@notification_permission_patch WebClient integration", () => {
    for (const inherited of [false, true]) {
        test(`permission lifecycle with inherited query=${inherited}`, async () => {
            const listeners = new Set();
            let attached = 0;
            let removed = 0;
            let granted = false;
            const status = {
                addEventListener(event, listener) {
                    expect(event).toBe("change");
                    attached++;
                    listeners.add(listener);
                },
                removeEventListener(event, listener) {
                    expect(event).toBe("change");
                    removed++;
                    expect(listeners.delete(listener)).toBe(true);
                },
            };
            const query = async () => status;
            const api = inherited
                ? Object.create({ query })
                : Object.defineProperty({}, "query", {
                      value: query,
                      writable: true,
                      configurable: true,
                      enumerable: false,
                  });
            const descriptor = Object.getOwnPropertyDescriptor(api, "query");
            await makeTestApp();
            patch(browser.navigator, { permissions: api });
            patch(WebClient.prototype, {
                get _canSendNativeNotification() {
                    return granted;
                },
                _subscribePush() {
                    expect.step("subscribe");
                },
                _unsubscribePush() {
                    expect.step("unsubscribe");
                },
            });
            await mountWebClient();
            expect(attached).toBe(1);
            expect(listeners.size).toBe(1);
            expect(api.query).toBe(query);
            expect(Object.getOwnPropertyDescriptor(api, "query")).toEqual(descriptor);
            granted = true;
            for (const listener of listeners) {
                listener(new Event("change"));
            }
            expect.verifySteps(["subscribe"]);
            granted = false;
            for (const listener of listeners) {
                listener(new Event("change"));
            }
            expect.verifySteps(["unsubscribe"]);
            destroyApp();
            expect(removed).toBe(1);
            expect(listeners.size).toBe(0);
            expect(Object.getOwnPropertyDescriptor(api, "query")).toEqual(descriptor);
        });
    }

    test("mounts without the permissions API", async () => {
        patch(browser.navigator, { permissions: undefined });
        const webClient = await mountWebClient();
        expect(webClient).toBeInstanceOf(WebClient);
        destroyApp();
    });
});
