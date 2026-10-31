import importlib.util
import json
import unittest
from pathlib import Path

spec = importlib.util.spec_from_file_location("readonly_policy", Path(__file__).parents[1] / "policy.py")
policy = importlib.util.module_from_spec(spec)
spec.loader.exec_module(policy)


class TestRuntimeQualification(unittest.TestCase):
    def setUp(self) -> None:
        self.identity = {
            "schema_version": 1,
            "product": "synthetic-product",
            "context": "synthetic",
            "instance": "testing",
            "environment_kind": "stable",
            "deployment_record_id": "deployment-a",
            "artifact_id": "artifact-a",
            "source_git_ref": "source-a",
        }

    def qualify(self, identity: dict | None = None, **overrides: str) -> dict:
        arguments = {
            "runtime": json.dumps(self.identity),
            "platform_instance": "testing",
            "database": "synthetic-database",
            "database_uuid": "synthetic-uuid",
            "copy_witness": "a" * 64,
        }
        return policy.qualify_runtime(identity or self.identity, **dict(arguments, **overrides))

    def test_requires_current_native_runtime(self) -> None:
        self.assertEqual(self.qualify()["product"], self.identity["product"])
        for field in ("product", "context", "instance", "deployment_record_id", "artifact_id", "source_git_ref"):
            with self.subTest(field=field), self.assertRaises(ValueError):
                self.qualify(dict(self.identity, **{field: "other"}))
        for runtime in ("null", "[]", "{}", "invalid"):
            with self.subTest(runtime=runtime), self.assertRaises(ValueError):
                self.qualify(runtime=runtime)

    def test_refuses_production_unknown_target_and_wrong_copy(self) -> None:
        for instance in ("", "prod", "production", "preview"):
            with self.subTest(instance=instance), self.assertRaises(ValueError):
                self.qualify(platform_instance=instance)
        for witness in ("", "old-copy", "g" * 64):
            with self.subTest(witness=witness), self.assertRaises(ValueError):
                self.qualify(copy_witness=witness)
        self.assertNotEqual(self.qualify(), self.qualify(copy_witness="b" * 64))
        with self.assertRaises(ValueError):
            self.qualify(database_uuid="")

    def test_preview_refresh_retains_owner_but_rejects_stale_caller(self) -> None:
        testing_owner = self.qualify()
        self.identity.update(
            environment_kind="preview", instance="preview-example", preview_id="preview-a", preview_generation_id="one"
        )
        first = self.qualify(platform_instance="preview", copy_witness="")
        old = dict(self.identity)
        self.identity["preview_generation_id"] = "two"
        self.assertEqual(first, self.qualify(platform_instance="preview", copy_witness=""))
        with self.assertRaises(ValueError):
            self.qualify(old, platform_instance="preview", copy_witness="")
        self.assertNotEqual(testing_owner, first)
        for field in ("preview_id", "preview_generation_id"):
            original = self.identity.pop(field)
            with self.assertRaises(ValueError):
                self.qualify(platform_instance="preview")
            self.identity[field] = original

    def test_revision_alias_and_observation_timestamp_are_not_new_owners(self) -> None:
        alias = dict(self.identity)
        alias["source_revision"] = alias.pop("source_git_ref")
        alias["deployed_at"] = "later observation"
        self.assertEqual(self.qualify(), self.qualify(alias))
        with self.assertRaises(ValueError):
            self.qualify(dict(alias, source_git_ref="different-source"))

    def test_login_is_stable_and_product_specific(self) -> None:
        login = policy.product_login(self.identity["product"])
        self.assertEqual(login, policy.product_login(self.identity["product"]))
        self.assertNotEqual(login, policy.product_login("another-product"))
