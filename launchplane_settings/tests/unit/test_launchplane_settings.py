import base64
import json
import os
from collections.abc import Iterator, Mapping
from contextlib import contextmanager

from odoo.exceptions import ValidationError

from ...models.launchplane_settings import (
    ODOO_INSTANCE_OVERRIDES_PAYLOAD_ENV_KEY,
    PLATFORM_INSTANCE_ENV_KEY,
    PRODUCTION_PLATFORM_INSTANCE,
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
class TestLaunchplaneSettings(UnitTestCase):
    @staticmethod
    def _payload_env(payload: Mapping[str, object]) -> dict[str, str]:
        encoded = base64.b64encode(json.dumps(payload, sort_keys=True).encode("utf-8")).decode("ascii")
        return {ODOO_INSTANCE_OVERRIDES_PAYLOAD_ENV_KEY: encoded}

    def _set_production_shopify_credentials(self) -> None:
        self.ConfigParameter.set_param("shopify.shop_url_key", "live-store")
        self.ConfigParameter.set_param("shopify.api_token", "live-token")
        self.ConfigParameter.set_param("shopify.webhook_key", "live-hook")

    def _assert_shopify_credentials_cleared(self) -> None:
        self.assertFalse(self.ConfigParameter.get_param("shopify.shop_url_key"))
        self.assertFalse(self.ConfigParameter.get_param("shopify.api_token"))
        self.assertFalse(self.ConfigParameter.get_param("shopify.webhook_key"))

    def _assert_production_shopify_credentials_kept(self) -> None:
        self.assertEqual(self.ConfigParameter.get_param("shopify.shop_url_key"), "live-store")
        self.assertEqual(self.ConfigParameter.get_param("shopify.api_token"), "live-token")
        self.assertEqual(self.ConfigParameter.get_param("shopify.webhook_key"), "live-hook")

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
            self.Settings.apply_from_env()

        self.assertEqual(self.ConfigParameter.get_param("test.value"), "False")

    def test_apply_shopify_overrides_from_payload_secret_binding_env(self) -> None:
        payload = {
            "schema_version": 1,
            "config_parameters": [],
            "addon_settings": [
                {
                    "addon": "shopify",
                    "setting": "action",
                    "value": {"source": "literal", "value": "apply"},
                },
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
            self.Settings.apply_from_env()

        self.assertEqual(self.ConfigParameter.get_param("shopify.shop_url_key"), "typed-store")
        self.assertEqual(self.ConfigParameter.get_param("shopify.api_token"), "token-from-secret")
        self.assertEqual(self.ConfigParameter.get_param("shopify.webhook_key"), "hook")
        self.assertEqual(self.ConfigParameter.get_param("shopify.api_version"), "2025-01")
        self.assertEqual(self.ConfigParameter.get_param("shopify.test_store"), "True")

    def test_payload_shopify_settings_without_action_are_rejected(self) -> None:
        self.ConfigParameter.set_param("shopify.shop_url_key", "existing-store")
        payload = {
            "schema_version": 1,
            "config_parameters": [],
            "addon_settings": [
                {
                    "addon": "shopify",
                    "setting": "shop_url_key",
                    "value": {"source": "literal", "value": "other-store"},
                },
            ],
        }

        with _set_env(self._payload_env(payload)):
            with self.assertRaises(ValidationError):
                self.Settings.apply_from_env()
        self.assertEqual(self.ConfigParameter.get_param("shopify.shop_url_key"), "existing-store")

    def test_apply_shopify_clear_action_from_payload(self) -> None:
        self.ConfigParameter.set_param("shopify.shop_url_key", "store")
        self.ConfigParameter.set_param("shopify.api_token", "token")
        self.ConfigParameter.set_param("shopify.webhook_key", "hook")
        self.ConfigParameter.set_param("shopify.api_version", "2025-01")

        payload = {
            "schema_version": 1,
            "config_parameters": [],
            "addon_settings": [
                {
                    "addon": "shopify",
                    "setting": "action",
                    "value": {"source": "literal", "value": "clear"},
                },
            ],
        }

        with _set_env(self._payload_env(payload)):
            self.Settings.apply_from_env()

        self.assertFalse(self.ConfigParameter.get_param("shopify.shop_url_key"))
        self.assertFalse(self.ConfigParameter.get_param("shopify.api_token"))
        self.assertFalse(self.ConfigParameter.get_param("shopify.webhook_key"))
        self.assertFalse(self.ConfigParameter.get_param("shopify.api_version"))

    def test_apply_from_env_rejects_invalid_payload(self) -> None:
        with _set_env({ODOO_INSTANCE_OVERRIDES_PAYLOAD_ENV_KEY: "not-base64"}):
            with self.assertRaises(ValidationError):
                self.Settings.apply_from_env()

    def test_non_production_without_payload_clears_shopify_credentials(self) -> None:
        for platform_instance in ("testing", "", None):
            with self.subTest(platform_instance=platform_instance):
                self._set_production_shopify_credentials()
                with _set_env(
                    {
                        ODOO_INSTANCE_OVERRIDES_PAYLOAD_ENV_KEY: None,
                        PLATFORM_INSTANCE_ENV_KEY: platform_instance,
                    }
                ):
                    self.Settings.apply_from_env()

                self._assert_shopify_credentials_cleared()

    def test_non_production_payload_without_shopify_clears_shopify_credentials(self) -> None:
        self._set_production_shopify_credentials()
        payload = {
            "schema_version": 1,
            "config_parameters": [
                {"key": "test.value", "value": {"source": "literal", "value": "kept"}},
            ],
            "addon_settings": [],
        }

        with _set_env({**self._payload_env(payload), PLATFORM_INSTANCE_ENV_KEY: "testing"}):
            self.Settings.apply_from_env()

        self._assert_shopify_credentials_cleared()
        self.assertEqual(self.ConfigParameter.get_param("test.value"), "kept")

    def test_non_production_explicit_shopify_apply_is_kept(self) -> None:
        self._set_production_shopify_credentials()
        payload = {
            "schema_version": 1,
            "config_parameters": [],
            "addon_settings": [
                {"addon": "shopify", "setting": setting, "value": {"source": "literal", "value": value}}
                for setting, value in (
                    ("action", "apply"),
                    ("shop_url_key", "dev-store"),
                    ("api_token", "dev-token"),
                    ("webhook_key", "dev-hook"),
                    ("api_version", "2025-01"),
                    ("test_store", True),
                )
            ],
        }

        with _set_env({**self._payload_env(payload), PLATFORM_INSTANCE_ENV_KEY: "testing"}):
            self.Settings.apply_from_env()

        self.assertEqual(self.ConfigParameter.get_param("shopify.shop_url_key"), "dev-store")
        self.assertEqual(self.ConfigParameter.get_param("shopify.api_token"), "dev-token")
        self.assertEqual(self.ConfigParameter.get_param("shopify.webhook_key"), "dev-hook")

    def test_production_without_shopify_action_keeps_shopify_credentials(self) -> None:
        payload_without_shopify = {"schema_version": 1, "config_parameters": [], "addon_settings": []}
        for payload_env in (
            {ODOO_INSTANCE_OVERRIDES_PAYLOAD_ENV_KEY: None},
            self._payload_env(payload_without_shopify),
        ):
            with self.subTest(payload_present=payload_env[ODOO_INSTANCE_OVERRIDES_PAYLOAD_ENV_KEY] is not None):
                self._set_production_shopify_credentials()
                with _set_env({**payload_env, PLATFORM_INSTANCE_ENV_KEY: PRODUCTION_PLATFORM_INSTANCE}):
                    self.Settings.apply_from_env()

                self._assert_production_shopify_credentials_kept()
