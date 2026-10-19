"""Keep the native applier and its compatibility helpers on the pure producer."""

import base64
import json
import os
from unittest.mock import patch

from odoo.exceptions import ValidationError

from ...models import launchplane_settings as adapter
from ...services import override_payload
from ..fixtures.base import UnitTestCase


class TestOverridePayloadIntegration(UnitTestCase):
    def test_native_projection_agrees_with_pure_resolver(self) -> None:
        variable = "SYNTHETIC_NATIVE_PAYLOAD_VALUE"
        environment = {variable: " raw synthetic value "}
        payload = {
            "config_parameters": [
                {"key": "test.pure.flag", "value": {"source": "literal", "value": " off "}},
                {"key": "test.pure.reference", "value": {"source": "secret_binding", "environment_variable": variable}},
            ]
        }
        expected = override_payload.resolve_config_parameters(payload, environment)
        with patch.dict(os.environ, environment):
            self.assertEqual(self.Settings._payload_config_param_overrides(payload), expected)

    def test_native_load_agrees_with_supplied_payload_decoder(self) -> None:
        payload = {"config_parameters": []}
        encoded = " \n" + base64.b64encode(json.dumps(payload).encode()).decode() + "\t "
        with patch.dict(os.environ, {override_payload.ODOO_INSTANCE_OVERRIDES_PAYLOAD_ENV_KEY: encoded}):
            self.assertEqual(adapter._load_override_payload(), override_payload.decode_payload(encoded))

    def test_native_decoder_and_projection_translate_producer_errors(self) -> None:
        malformed = "not-base64"
        with self.assertRaises(override_payload.OverridePayloadError) as expected:
            override_payload.decode_payload(malformed)
        with patch.dict(os.environ, {override_payload.ODOO_INSTANCE_OVERRIDES_PAYLOAD_ENV_KEY: malformed}):
            with self.assertRaises(ValidationError) as actual:
                adapter._load_override_payload()
        self.assertEqual(str(actual.exception), str(expected.exception))
        for payload in ({"config_parameters": {}}, {"config_parameters": [{"key": "test.invalid"}]}):
            with self.subTest(payload=payload):
                with self.assertRaises(override_payload.OverridePayloadError) as expected:
                    override_payload.resolve_config_parameters(payload, {})
                with self.assertRaises(ValidationError) as actual:
                    self.Settings._payload_config_param_overrides(payload)
                self.assertEqual(str(actual.exception), str(expected.exception))

    def test_private_value_and_items_entrypoints_keep_odoo_errors(self) -> None:
        malformed = {"addon_settings": [None]}
        with self.assertRaises(override_payload.OverridePayloadError) as expected:
            override_payload._payload_items(malformed, "addon_settings")
        with self.assertRaises(ValidationError) as actual:
            adapter._payload_items(malformed, "addon_settings")
        self.assertEqual(str(actual.exception), str(expected.exception))
        with self.assertRaises(override_payload.OverridePayloadError) as expected:
            override_payload._payload_value_for_setting(raw_value={}, override_name="synthetic", environment={})
        with self.assertRaises(ValidationError) as actual:
            adapter._payload_value_for_setting(raw_value={}, override_name="synthetic")
        self.assertEqual(str(actual.exception), str(expected.exception))

    def test_native_application_preserves_omitted_parameters(self) -> None:
        existing = "test.pure.existing"
        self.ConfigParameter.set_param(existing, "retained")
        self.Settings._apply_config_param_overrides(
            payload={
                "config_parameters": [
                    {"key": "test.pure.added", "value": {"source": "literal", "value": "new"}},
                ]
            }
        )
        self.assertEqual(self.ConfigParameter.get_param(existing), "retained")
        self.assertEqual(self.ConfigParameter.get_param("test.pure.added"), "new")
