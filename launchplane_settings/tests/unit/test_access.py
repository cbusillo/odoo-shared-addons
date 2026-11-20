import base64
import json
import os
from unittest.mock import patch

from odoo.exceptions import AccessError
from odoo.service.model import call_kw
from odoo.tests import new_test_user

from ...models.launchplane_settings import ODOO_INSTANCE_OVERRIDES_PAYLOAD_ENV_KEY
from ..common_imports import common
from ..fixtures.base import UnitTestCase


@common.tagged(*common.UNIT_TAGS)
class TestLaunchplaneSettingsAccess(UnitTestCase):
    def test_rpc_users_cannot_apply_runtime_settings(self) -> None:
        key = "launchplane_settings.rpc_access_fixture"
        payload = {
            "schema_version": 1,
            "config_parameters": [{"key": key, "value": {"source": "literal", "value": "changed"}}],
            "addon_settings": [],
        }
        encoded = base64.b64encode(json.dumps(payload).encode()).decode()

        for group in ("base.group_user", "base.group_portal"):
            user = new_test_user(self.env, login=f"launchplane-settings-{group}", groups=group)
            self.ConfigParameter.search([("key", "=", key)]).unlink()
            blocked = False
            with patch.dict(os.environ, {ODOO_INSTANCE_OVERRIDES_PAYLOAD_ENV_KEY: encoded}):
                try:
                    call_kw(self.Settings.with_user(user), "apply_from_env", [[]], {})
                except AccessError:
                    blocked = True

            with self.subTest(group=group):
                self.assertFalse(self.ConfigParameter.get_str(key))
                self.assertTrue(blocked)
