import base64
import json
import os
from collections.abc import Iterator, Mapping
from contextlib import contextmanager

from ...models.environment_overrides import ODOO_INSTANCE_OVERRIDES_PAYLOAD_ENV_KEY
from ..common_imports import common
from ..fixtures.base import UnitTestCase


@contextmanager
def _set_env(values: Mapping[str, str | None]) -> Iterator[None]:
    previous = {key: os.environ.get(key) for key in values}
    for key, value in values.items():
        if value is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = value
    try:
        yield
    finally:
        for key, value in previous.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


@common.tagged(*common.UNIT_TAGS)
class TestEnvironmentOverrides(UnitTestCase):
    @staticmethod
    def _payload_env(payload: Mapping[str, object]) -> dict[str, str]:
        encoded = base64.b64encode(json.dumps(payload, sort_keys=True).encode("utf-8")).decode("ascii")
        return {ODOO_INSTANCE_OVERRIDES_PAYLOAD_ENV_KEY: encoded}

    def test_environment_overrides_delegates_to_launchplane_settings(self) -> None:
        payload = {
            "schema_version": 1,
            "config_parameters": [
                {
                    "key": "test.value",
                    "value": {"source": "literal", "value": "from-launchplane-settings"},
                }
            ],
            "addon_settings": [],
        }

        with _set_env(self._payload_env(payload)):
            self.Overrides.apply_from_env()

        self.assertEqual(self.ConfigParameter.get_param("test.value"), "from-launchplane-settings")

    def test_environment_overrides_keeps_legacy_env_bridge_until_callers_migrate(self) -> None:
        with _set_env({"ENV_OVERRIDE_CONFIG_PARAM__TEST__VALUE": "from-legacy-env"}):
            self.Overrides.apply_from_env()

        self.assertEqual(self.ConfigParameter.get_param("test.value"), "from-legacy-env")
