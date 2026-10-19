"""Load the installed producer directly, independently of Odoo and addon imports."""

import base64
import builtins
import importlib.util
import json
import os
import sys
import unittest
from collections.abc import Mapping
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch

if __package__:
    from ..fixtures.base import UnitTestCase as PayloadTestCase
else:
    PayloadTestCase = unittest.TestCase


class TestOverridePayload(PayloadTestCase):
    def setUp(self) -> None:
        super().setUp()
        path = Path(__file__).resolve().parents[2] / "services" / "override_payload.py"
        name = "standalone_launchplane_override_payload"
        spec = importlib.util.spec_from_file_location(name, path)
        assert spec is not None
        self.producer = importlib.util.module_from_spec(spec)
        program = compile(path.read_bytes(), str(path), "exec")
        sys.modules[name] = self.producer
        self.addCleanup(sys.modules.pop, name, None)
        original_import = builtins.__import__

        def guarded_import(name: str, *args, **kwargs):
            if name.split(".")[0] in {"odoo", "launchplane_settings", "pymysql", "psycopg2"}:
                raise AssertionError("Pure producer imported a runtime dependency")
            return original_import(name, *args, **kwargs)

        class ForbiddenEnvironment(Mapping):
            def __getitem__(self, key):
                raise AssertionError("Pure producer read the global environment")

            def __iter__(self):
                raise AssertionError("Pure producer enumerated the global environment")

            def __len__(self):
                raise AssertionError("Pure producer inspected the global environment")

        with (
            patch("builtins.__import__", side_effect=guarded_import),
            patch("builtins.open", side_effect=AssertionError("Pure producer opened a file")),
            patch.object(Path, "open", side_effect=AssertionError("Pure producer opened a path")),
            patch.object(os, "open", side_effect=AssertionError("Pure producer opened a descriptor")),
            patch.object(os, "environ", ForbiddenEnvironment()),
        ):
            exec(program, self.producer.__dict__)

    @staticmethod
    def encoded(payload: object) -> str:
        return base64.b64encode(json.dumps(payload).encode()).decode()

    @staticmethod
    def literal(key: str, value: object) -> dict[str, object]:
        return {"key": key, "value": {"source": "literal", "value": value}}

    @staticmethod
    def reference(key: str, variable: str) -> dict[str, object]:
        return {"key": key, "value": {"source": "secret_binding", "environment_variable": variable}}

    def test_decode_blank_and_object_without_reading_the_environment(self) -> None:
        for raw in ("", " \n\t "):
            with self.subTest(raw=raw):
                self.assertIsNone(self.producer.decode_payload(raw))
        payload = {"config_parameters": [self.literal("sample.flag", False)]}
        self.assertEqual(self.producer.decode_payload(" \n" + self.encoded(payload) + "\t "), payload)

    def test_decode_rejects_invalid_encoding_json_and_nonobjects(self) -> None:
        invalid = (
            "not-base64",
            base64.b64encode(b"not-json").decode(),
            base64.b64encode(b"\xff").decode(),
            self.encoded([]),
            self.encoded(None),
            self.encoded("text"),
        )
        for raw in invalid:
            with self.subTest(raw=raw), self.assertRaises(self.producer.OverridePayloadError):
                self.producer.decode_payload(raw)

    def test_literal_normalization_keeps_boolean_and_scalar_semantics(self) -> None:
        for raw, expected in (
            (True, "True"),
            (False, "False"),
            ("", "False"),
            (" 0 ", "False"),
            (0, "False"),
            (1, "True"),
            (" On ", "True"),
            ("No", "False"),
            ("off", "False"),
            (" yes ", "True"),
            (" 3.5 ", "3.5"),
            (None, "None"),
            (" [1, 2] ", "[1, 2]"),
        ):
            with self.subTest(raw=raw):
                payload = {"config_parameters": [self.literal("sample.value", raw)]}
                self.assertEqual(self.producer.resolve_config_parameters(payload, {}), {"sample.value": expected})

    def test_secret_reference_keeps_raw_string_and_checks_presence(self) -> None:
        key, variable = "sample.password", "SYNTHETIC_VALUE"
        payload = {"config_parameters": [self.reference(key, variable)]}
        for raw in (" \t0\n", "false", "", " synthetic-only "):
            with self.subTest(raw=raw):
                self.assertEqual(self.producer.resolve_config_parameters(payload, {variable: raw}), {key: raw})
        with self.assertRaises(self.producer.OverridePayloadError) as error:
            self.producer.resolve_config_parameters(payload, {})
        self.assertIn(variable, str(error.exception))

    def test_duplicate_keys_keep_last_value_and_first_insertion_order(self) -> None:
        payload = {
            "config_parameters": [
                self.literal(" Sample.One ", "first"),
                self.literal("sample.two", "middle"),
                self.literal("SAMPLE.ONE", "last"),
            ]
        }
        result = self.producer.resolve_config_parameters(payload, {})
        self.assertEqual(result, {"sample.one": "last", "sample.two": "middle"})
        self.assertEqual(tuple(result), ("sample.one", "sample.two"))
        payload["config_parameters"].insert(0, self.reference("sample.one", "MISSING_SYNTHETIC"))
        with self.assertRaises(self.producer.OverridePayloadError):
            self.producer.resolve_config_parameters(payload, {})

    def test_selection_skips_only_unrelated_environment_reads(self) -> None:
        key, variable = "sample.selected", "SYNTHETIC_SELECTED"
        payload = {
            "config_parameters": [
                self.reference("unrelated.password", "FORBIDDEN_SYNTHETIC"),
                self.reference(key, variable),
            ]
        }

        class SelectedEnvironment(Mapping):
            def __getitem__(self, requested):
                if requested != variable:
                    raise AssertionError("Projection read an unselected environment value")
                return " synthetic-only "

            def __iter__(self):
                raise AssertionError("Projection enumerated environment values")

            def __len__(self):
                raise AssertionError("Projection inspected the environment")

        environment = SelectedEnvironment()
        self.assertEqual(
            self.producer.resolve_config_parameters(payload, environment, keys=(key,)), {key: " synthetic-only "}
        )
        self.assertEqual(self.producer.resolve_config_parameters(payload, environment, keys=()), {})
        with self.assertRaises(self.producer.OverridePayloadError):
            self.producer.resolve_config_parameters(payload, {})

    def test_selection_validates_all_value_structures_without_environment_reads(self) -> None:
        class NoEnvironmentReads(Mapping):
            def __getitem__(self, key):
                raise AssertionError("Structural validation read the environment")

            def __iter__(self):
                raise AssertionError("Structural validation enumerated the environment")

            def __len__(self):
                raise AssertionError("Structural validation inspected the environment")

        for value in (
            None,
            [],
            {},
            {"source": "unsupported"},
            {"source": "literal"},
            {"source": "secret_binding"},
            {"source": "secret_binding", "environment_variable": " \t "},
        ):
            payload = {
                "config_parameters": [
                    {"key": "unrelated.value", "value": value},
                    self.literal("sample.selected", "kept"),
                ]
            }
            with self.subTest(value=value):
                with self.assertRaises(self.producer.OverridePayloadError) as expected:
                    self.producer.resolve_config_parameters(payload, {})
                for keys in ((), ("sample.selected",)):
                    with self.subTest(keys=keys), self.assertRaises(self.producer.OverridePayloadError) as actual:
                        self.producer.resolve_config_parameters(payload, NoEnvironmentReads(), keys=keys)
                    self.assertEqual(str(actual.exception), str(expected.exception))

    def test_selection_normalizes_names_and_rejects_invalid_collections(self) -> None:
        key = "sample.selected"
        payload = {"config_parameters": [self.literal(key, "kept")]}
        for keys in ((" SAMPLE.Selected ",), [key.upper()], {"\t" + key + "\n"}):
            with self.subTest(keys=keys):
                self.assertEqual(self.producer.resolve_config_parameters(payload, {}, keys=keys), {key: "kept"})
        for keys in (
            key,
            key.encode(),
            bytearray(key.encode()),
            memoryview(key.encode()),
            0,
            (None,),
            (1,),
            ("",),
            (" \t ",),
            (key, None),
        ):
            with self.subTest(keys=keys), self.assertRaises(self.producer.OverridePayloadError):
                self.producer.resolve_config_parameters(payload, {}, keys=keys)

    def test_omissions_remain_omitted_and_inputs_are_not_mutated(self) -> None:
        for payload in (None, {}, {"config_parameters": None}, {"config_parameters": []}):
            with self.subTest(payload=payload):
                self.assertEqual(self.producer.resolve_config_parameters(payload, {"IGNORED": "synthetic"}), {})
        payload = {"config_parameters": [self.literal("sample.present", "value")]}
        before = deepcopy(payload)
        self.assertEqual(self.producer.resolve_config_parameters(payload, {}, keys=("sample.absent",)), {})
        self.assertEqual(payload, before)

    def test_shapes_missing_fields_and_unsupported_sources_are_rejected(self) -> None:
        for payload in (
            {"config_parameters": {}},
            {"config_parameters": [None]},
            {"config_parameters": [{"key": " "}]},
            {"config_parameters": [{"key": "sample.key"}]},
            {"config_parameters": [{"key": "sample.key", "value": {"source": "literal"}}]},
            {"config_parameters": [{"key": "sample.key", "value": {"source": "secret_binding"}}]},
            {"config_parameters": [{"key": "sample.key", "value": {"source": "runtime_environment"}}]},
        ):
            with self.subTest(payload=payload), self.assertRaises(self.producer.OverridePayloadError):
                self.producer.resolve_config_parameters(payload, {})


if __name__ == "__main__":
    unittest.main()
