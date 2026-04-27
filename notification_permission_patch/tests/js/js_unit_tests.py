from ..common_imports import common


@common.tagged(*common.JS_TAGS, "notification_permission_patch")
class TestNotificationPermissionPatchJs(common.HttpCase):
    def test_notification_permission_patch_js(self) -> None:
        url = "/web/tests?headless=1&loglevel=2&timeout=30000&filter=%40notification_permission_patch&autorun=1"
        self.browser_js(url, "", "", login="admin", timeout=60)

