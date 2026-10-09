import { describe, expect, test } from "@odoo/hoot";

import {
  observeNotificationPermissionChanges,
  registerNotificationPermissionObserver,
} from "@notification_permission_patch/js/notification_permission_patch";

describe("@notification_permission_patch notification permission patch", () => {
  test("uses native event listeners when available", () => {
    const onPermissionChange = () => expect.step("permission changed");
    const permissionStatus = {
      addEventListener(event, callback) {
        expect(event).toBe("change");
        expect(callback).toBe(onPermissionChange);
        expect.step("attached");
      },
      removeEventListener(event, callback) {
        expect(event).toBe("change");
        expect(callback).toBe(onPermissionChange);
        expect.step("removed");
      },
    };

    const cleanup = observeNotificationPermissionChanges(
      permissionStatus,
      onPermissionChange,
    );
    expect.verifySteps(["attached"]);
    cleanup();
    expect.verifySteps(["removed"]);
  });

  test("falls back to onchange when event listeners are unavailable", () => {
    const previousOnchange = () => expect.step("previous handler");
    const permissionStatus = { onchange: previousOnchange };
    const onPermissionChange = () => expect.step("permission changed");

    const cleanup = observeNotificationPermissionChanges(
      permissionStatus,
      onPermissionChange,
    );
    permissionStatus.onchange({ type: "change" });
    expect.verifySteps(["previous handler", "permission changed"]);

    cleanup();
    expect(permissionStatus.onchange).toBe(previousOnchange);
  });

  test("degrades gracefully when onchange is readonly", () => {
    const permissionStatus = {};
    Object.defineProperty(permissionStatus, "onchange", {
      configurable: true,
      get() {
        return null;
      },
      set() {
        throw new TypeError("Attempted to assign to readonly property.");
      },
    });

    const cleanup = observeNotificationPermissionChanges(
      permissionStatus,
      () => expect.step("permission changed"),
    );
    expect(() => cleanup()).not.toThrow();
    expect.verifySteps([]);
  });

  test("does not attach an observer after teardown", async () => {
    const permissionStatus = {
      addEventListener: () => expect.step("attached"),
      removeEventListener: () => expect.step("removed"),
    };

    const cleanup = await registerNotificationPermissionObserver(
      Promise.resolve(permissionStatus),
      () => expect.step("permission changed"),
      () => true,
    );
    expect(() => cleanup()).not.toThrow();
    expect.verifySteps([]);
  });
});
