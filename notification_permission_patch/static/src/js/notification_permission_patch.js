import { onWillDestroy } from "@odoo/owl";
import { browser } from "@web/core/browser/browser";
import { patch } from "@web/core/utils/patch";
import { WebClient } from "@web/webclient/webclient";

export function observeNotificationPermissionChanges(permissionStatus, onPermissionChange) {
    if (!permissionStatus || typeof onPermissionChange !== "function") {
        return () => {};
    }

    if (typeof permissionStatus.addEventListener === "function") {
        permissionStatus.addEventListener("change", onPermissionChange);
        return () => permissionStatus.removeEventListener?.("change", onPermissionChange);
    }

    if (!("onchange" in permissionStatus)) {
        return () => {};
    }

    const previousOnchange = permissionStatus.onchange;
    const wrappedOnchange = (event) => {
        if (typeof previousOnchange === "function") {
            previousOnchange.call(permissionStatus, event);
        }
        onPermissionChange(event);
    };

    try {
        permissionStatus.onchange = wrappedOnchange;
    } catch {
        return () => {};
    }

    return () => {
        try {
            if (permissionStatus.onchange === wrappedOnchange) {
                permissionStatus.onchange = previousOnchange ?? null;
            }
        } catch {}
    };
}

export async function registerNotificationPermissionObserver(
    permissionQueryPromise,
    onPermissionChange,
    wasDestroyed = () => false,
) {
    try {
        const permissionStatus = await permissionQueryPromise;
        if (wasDestroyed()) {
            return () => {};
        }
        const removeObserver = observeNotificationPermissionChanges(
            permissionStatus,
            onPermissionChange,
        );
        if (wasDestroyed()) {
            removeObserver();
            return () => {};
        }
        return removeObserver;
    } catch {
        return () => {};
    }
}

// noinspection JSUnusedGlobalSymbols
patch(WebClient.prototype, {
    setup() {
        const permissionsApi = browser.navigator?.permissions;
        const queryPermission = permissionsApi?.query;
        if (!queryPermission) {
            super.setup();
            return;
        }
        permissionsApi.query = (descriptor) =>
            descriptor?.name === "notifications"
                ? Promise.resolve({ addEventListener() {}, removeEventListener() {} })
                : queryPermission.call(permissionsApi, descriptor);
        try {
            super.setup();
        } finally {
            permissionsApi.query = queryPermission;
        }

        let removePermissionObserver = () => {};
        let destroyed = false;
        const onPermissionChange = () => {
            if (this._canSendNativeNotification) {
                this._subscribePush();
            } else {
                this._unsubscribePush();
            }
        };

        registerNotificationPermissionObserver(
            queryPermission.call(permissionsApi, { name: "notifications" }),
            onPermissionChange,
            () => destroyed,
        ).then((cleanup) => {
            if (destroyed) {
                cleanup();
                return;
            }
            removePermissionObserver = cleanup;
        });

        onWillDestroy(() => {
            destroyed = true;
            removePermissionObserver();
        });
    },
});
