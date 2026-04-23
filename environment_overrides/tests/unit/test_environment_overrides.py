import base64
import json
import os
from collections.abc import Iterator, Mapping
from contextlib import contextmanager

from odoo.exceptions import ValidationError

from ...models.environment_overrides import (
    ODOO_INSTANCE_OVERRIDES_PAYLOAD_ENV_KEY,
    _normalize_config_param_value,
    _parse_boolean,
)
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

    def test_normalize_config_param_value(self) -> None:
        self.assertEqual(_normalize_config_param_value(" true "), "True")
        self.assertEqual(_normalize_config_param_value("false"), "False")
        self.assertEqual(_normalize_config_param_value(" 123 "), "123")

    def test_normalize_config_param_value_preserves_json_like_values(self) -> None:
        self.assertEqual(_normalize_config_param_value("[1, 2]"), "[1, 2]")
        self.assertEqual(_normalize_config_param_value('{"mode": "test"}'), '{"mode": "test"}')
        self.assertEqual(_normalize_config_param_value("{not json}"), "{not json}")

    def test_parse_boolean(self) -> None:
        self.assertTrue(_parse_boolean(None, default=True))
        self.assertFalse(_parse_boolean(None, default=False))
        self.assertTrue(_parse_boolean("yes", default=False))
        self.assertFalse(_parse_boolean("0", default=True))

    def test_parse_boolean_uses_default_for_unknown_values(self) -> None:
        self.assertTrue(_parse_boolean("maybe", default=True))
        self.assertFalse(_parse_boolean("maybe", default=False))

    def test_apply_config_param_overrides(self) -> None:
        with _set_env({"ENV_OVERRIDE_CONFIG_PARAM__TEST__VALUE": "true"}):
            self.Overrides._apply_config_param_overrides()

        self.assertEqual(self.ConfigParameter.get_param("test.value"), "True")

    def test_apply_config_param_overrides_from_payload(self) -> None:
        payload = {
            "schema_version": 1,
            "config_parameters": [
                {
                    "key": "test.value",
                    "value": {
                        "source": "literal",
                        "value": False,
                    },
                }
            ],
            "addon_settings": [],
        }

        with _set_env(self._payload_env(payload)):
            self.Overrides.apply_from_env()

        self.assertEqual(self.ConfigParameter.get_param("test.value"), "False")

    def test_payload_config_param_overrides_take_precedence_over_legacy_env(self) -> None:
        payload = {
            "schema_version": 1,
            "config_parameters": [
                {
                    "key": "test.value",
                    "value": {
                        "source": "literal",
                        "value": "from-payload",
                    },
                }
            ],
            "addon_settings": [],
        }

        with _set_env(
            {
                **self._payload_env(payload),
                "ENV_OVERRIDE_CONFIG_PARAM__TEST__VALUE": "from-env",
            }
        ):
            self.Overrides.apply_from_env()

        self.assertEqual(self.ConfigParameter.get_param("test.value"), "from-payload")

    def test_shopify_overrides_rejects_production_urls(self) -> None:
        env_values = {
            "ENV_OVERRIDE_SHOPIFY__SHOP_URL_KEY": "prod-store",
            "ENV_OVERRIDE_SHOPIFY__API_TOKEN": "token",
            "ENV_OVERRIDE_SHOPIFY__WEBHOOK_KEY": "hook",
            "ENV_OVERRIDE_SHOPIFY__API_VERSION": "2025-01",
            "ENV_OVERRIDE_SHOPIFY__TEST_STORE": "true",
            "ENV_OVERRIDE_SHOPIFY__PRODUCTION_INDICATORS": "prod",
        }
        with _set_env(env_values):
            with self.assertRaises(ValidationError):
                self.Overrides._apply_shopify_overrides()

    def test_shopify_overrides_clears_config_when_incomplete(self) -> None:
        self.ConfigParameter.set_param("shopify.shop_url_key", "store")
        self.ConfigParameter.set_param("shopify.api_token", "token")
        self.ConfigParameter.set_param("shopify.webhook_key", "hook")
        self.ConfigParameter.set_param("shopify.api_version", "2025-01")

        env_values = {
            "ENV_OVERRIDE_SHOPIFY__SHOP_URL_KEY": None,
            "ENV_OVERRIDE_SHOPIFY__API_TOKEN": "token",
            "ENV_OVERRIDE_SHOPIFY__WEBHOOK_KEY": None,
            "ENV_OVERRIDE_SHOPIFY__API_VERSION": None,
            "ENV_OVERRIDE_SHOPIFY__TEST_STORE": None,
            "ENV_OVERRIDE_SHOPIFY__PRODUCTION_INDICATORS": None,
        }
        with _set_env(env_values):
            self.Overrides._apply_shopify_overrides()

        self.assertFalse(self.ConfigParameter.get_param("shopify.shop_url_key"))
        self.assertFalse(self.ConfigParameter.get_param("shopify.api_token"))
        self.assertFalse(self.ConfigParameter.get_param("shopify.webhook_key"))
        self.assertFalse(self.ConfigParameter.get_param("shopify.api_version"))

    def test_apply_shopify_overrides_from_payload_secret_binding_env(self) -> None:
        payload = {
            "schema_version": 1,
            "config_parameters": [],
            "addon_settings": [
                {
                    "addon": "shopify",
                    "setting": "shop_url_key",
                    "value": {"source": "literal", "value": "typed-store"},
                },
                {
                    "addon": "shopify",
                    "setting": "api_token",
                    "value": {
                        "source": "secret_binding",
                        "secret_binding_id": "binding-shopify-token",
                        "environment_variable": "SHOPIFY_TOKEN_FROM_SECRET",
                    },
                },
                {
                    "addon": "shopify",
                    "setting": "webhook_key",
                    "value": {"source": "literal", "value": "hook"},
                },
                {
                    "addon": "shopify",
                    "setting": "api_version",
                    "value": {"source": "literal", "value": "2025-01"},
                },
                {
                    "addon": "shopify",
                    "setting": "test_store",
                    "value": {"source": "literal", "value": True},
                },
            ],
        }

        with _set_env(
            {
                **self._payload_env(payload),
                "SHOPIFY_TOKEN_FROM_SECRET": "token-from-secret",
            }
        ):
            self.Overrides.apply_from_env()

        self.assertEqual(self.ConfigParameter.get_param("shopify.shop_url_key"), "typed-store")
        self.assertEqual(self.ConfigParameter.get_param("shopify.api_token"), "token-from-secret")
        self.assertEqual(self.ConfigParameter.get_param("shopify.webhook_key"), "hook")
        self.assertEqual(self.ConfigParameter.get_param("shopify.api_version"), "2025-01")
        self.assertEqual(self.ConfigParameter.get_param("shopify.test_store"), "True")

    def test_apply_from_env_rejects_invalid_payload(self) -> None:
        with _set_env({ODOO_INSTANCE_OVERRIDES_PAYLOAD_ENV_KEY: "not-base64"}):
            with self.assertRaises(ValidationError):
                self.Overrides.apply_from_env()
