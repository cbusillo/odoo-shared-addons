from odoo.exceptions import ValidationError

from ...models.external_id_mixin import ExternalIdMixin
from ...models.external_reference import ExternalResourceName, ExternalSystemCode
from ..common_imports import common
from ..fixtures.base import UnitTestCase
from ..fixtures.factories import ExternalSystemFactory


class TestSystemCode(ExternalSystemCode):
    CATALOG = "catalog"


class TestResourceName(ExternalResourceName):
    PRODUCT = "product"


@common.tagged(*common.UNIT_TAGS)
class TestExternalIdMixin(UnitTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.sample_system = ExternalSystemFactory.create(
            self.env,
            name="Sample",
            code="sample",
            reuse_existing=True,
        )
        self.catalog_system = ExternalSystemFactory.create(
            self.env,
            name="Catalog",
            code="catalog",
            reuse_existing=True,
        )

    def _create_fixture(self, name: str) -> "odoo.model.external_id_fixture":
        return self.FixtureRecord.create({"name": name})

    def _use_test_catalog_urls(self) -> None:
        self.catalog_system.url = "https://store.example.test"
        self.env["external.system.url"].create(
            [
                {
                    "name": "Admin",
                    "code": "product_admin",
                    "system_id": self.catalog_system.id,
                    "resource": "product",
                    "base_url": "https://admin.example.test",
                    "template": "{base}/products/{id}",
                },
                {
                    "name": "Store",
                    "code": "product_store",
                    "system_id": self.catalog_system.id,
                    "resource": "product",
                    "template": "{base}/products/{id}",
                },
            ]
        )

    def test_fluent_id_assignment_and_read(self) -> None:
        record = self._create_fixture("Fluent Record")

        record.external.sample.default.id = "123456789012345678"

        self.assertEqual(record.external.sample.default.id, "123456789012345678")
        self.assertEqual(
            record.external.sample.default.record.external_id, "123456789012345678"
        )

    def test_fluent_resource_exposes_external_id_fields(self) -> None:
        record = self._create_fixture("Field Proxy Record")
        record.external.sample.default.id = "222222222222222222"

        record.external.sample.default.notes = "Needs review"

        self.assertEqual(record.external.sample.default.notes, "Needs review")
        self.assertTrue(record.external.sample.default.active)
        self.assertEqual(
            record.external.sample.default.external_id, "222222222222222222"
        )

    def test_fluent_resource_hides_archived_mapping_by_default(self) -> None:
        record = self._create_fixture("Archived Fluent Record")
        record.external.sample.default.id = "222222222222222222"
        record.external.sample.default.notes = "Needs review"

        record.external.sample.default.active = False

        self.assertFalse(record.external.sample.default)
        self.assertIsNone(record.external.sample.default.id)
        self.assertFalse(record.external.sample.default.external_id)
        self.assertFalse(record.external.sample.default.notes)
        self.assertFalse(record.external.sample.default.active)
        self.assertEqual(record.external.sample.default.id_any, "222222222222222222")
        self.assertEqual(
            record.external.sample.default.record_any.external_id, "222222222222222222"
        )
        self.assertEqual(
            record.external.sample.default.record_any.notes, "Needs review"
        )
        self.assertFalse(record.external.sample.default.record_any.active)

    def test_fluent_resource_can_clear_id_with_none(self) -> None:
        record = self._create_fixture("Clear Fluent Record")
        record.external.catalog.product.id = "123456"

        record.external.catalog.product.id = None

        self.assertIsNone(record.external.catalog.product.id)
        self.assertFalse(record.external.catalog.product.record_any.active)

    def test_fluent_model_api_get_returns_record(self) -> None:
        record = self._create_fixture("Lookup Record")
        record.external.sample.default.id = "333333333333333333"

        found_record = self.FixtureRecord.external.sample.default.get(
            "333333333333333333"
        )

        self.assertEqual(found_record, record)

    def test_fluent_model_api_bracket_lookup_returns_record(self) -> None:
        record = self._create_fixture("Bracket Lookup Record")
        record.external.sample.default.id = "343434343434343434"

        found_record = self.FixtureRecord.external_lookup.sample.default[
            "343434343434343434"
        ]

        self.assertEqual(found_record, record)

    def test_domain_by_external_id_builds_searchable_domain(self) -> None:
        record = self._create_fixture("Domain Lookup Record")
        record.external.sample.default.id = "353535353535353535"

        found_record = self.FixtureRecord.search(
            self.FixtureRecord.domain_by_external_id("sample", "353535353535353535"),
            limit=1,
        )

        self.assertEqual(found_record, record)

    def test_map_by_external_id_returns_lookup_for_model(self) -> None:
        first_record = self._create_fixture("First Generic Map Record")
        second_record = self._create_fixture("Second Generic Map Record")
        first_record.external.sample.default.id = "363636363636363636"
        second_record.external.sample.default.id = "373737373737373737"

        mapping = self.FixtureRecord.map_by_external_id(
            "sample",
            ["363636363636363636", "373737373737373737", "383838383838383838"],
        )

        self.assertEqual(mapping["363636363636363636"], first_record)
        self.assertEqual(mapping["373737373737373737"], second_record)
        self.assertNotIn("383838383838383838", mapping)

    def test_fluent_model_api_record_returns_external_id_record(self) -> None:
        record = self._create_fixture("Record Lookup")
        record.external.sample.default.id = "444444444444444444"

        external_id_record = self.FixtureRecord.external.sample.default.record(
            "444444444444444444"
        )

        self.assertEqual(external_id_record.res_model, "external.id.fixture")
        self.assertEqual(external_id_record.res_id, record.id)

    def test_fluent_model_api_get_or_create_reuses_archived_orphan(self) -> None:
        original_record = self._create_fixture("Archived Orphan")
        external_id_record = self.ExternalId.create(
            {
                "res_model": "external.id.fixture",
                "res_id": original_record.id + 999999,
                "system_id": self.sample_system.id,
                "external_id": "archived-id",
                "active": False,
            }
        )

        found_record = self.FixtureRecord.external.sample.default.get_or_create(
            "archived-id",
            {"name": "Recovered Archived Orphan"},
        )

        external_id_record.invalidate_recordset()
        self.assertTrue(external_id_record.active)
        self.assertEqual(external_id_record.res_id, found_record.id)
        self.assertEqual(found_record.name, "Recovered Archived Orphan")

    def test_get_or_create_by_external_id_skips_redundant_write(self) -> None:
        record = self._create_fixture("Stable Name")
        record.external.sample.default.id = "101010101010101010"

        with common.patch.object(
            type(record), "write", wraps=type(record).write
        ) as mock_write:
            found_record = self.FixtureRecord.get_or_create_by_external_id(
                "sample",
                "101010101010101010",
                {"name": "Stable Name"},
            )

        self.assertEqual(found_record, record)
        mock_write.assert_not_called()

    def test_get_or_create_by_external_id_rejects_unknown_fields(self) -> None:
        record = self._create_fixture("Known Record")
        record.external.sample.default.id = "121212121212121212"

        with self.assertRaises(ValueError):
            self.FixtureRecord.get_or_create_by_external_id(
                "sample",
                "121212121212121212",
                {"missing_field": "value"},
            )

    def test_write_if_changed_supports_many2many_updates(self) -> None:
        partner = self.env["res.partner"].create({"name": "Tagged Partner"})
        category = self.env["res.partner.category"].create({"name": "VIP"})

        changed = ExternalIdMixin._write_if_changed(
            partner,
            {"category_id": [(6, 0, [category.id])]},
        )

        self.assertTrue(changed)
        self.assertEqual(partner.category_id, category)

    def test_fluent_model_api_map_returns_lookup_by_external_id(self) -> None:
        first_record = self._create_fixture("First Map Record")
        second_record = self._create_fixture("Second Map Record")
        first_record.external.sample.default.id = "555555555555555555"
        second_record.external.sample.default.id = "666666666666666666"

        mapping = self.FixtureRecord.external.sample.default.map(
            [
                "555555555555555555",
                "666666666666666666",
                "777777777777777777",
            ]
        )

        self.assertEqual(mapping["555555555555555555"], first_record)
        self.assertEqual(mapping["666666666666666666"], second_record)
        self.assertNotIn("777777777777777777", mapping)

    def test_bound_external_id_property_uses_declared_binding(self) -> None:
        record = self._create_fixture("Bound Record")

        record.external_reference.id = "777777777777777777"

        self.assertEqual(record.get_bound_external_id(), "777777777777777777")
        self.assertEqual(record.external_reference.id, "777777777777777777")
        self.assertEqual(record.external.sample.default.id, "777777777777777777")

    def test_copy_does_not_duplicate_external_ids(self) -> None:
        original_record = self._create_fixture("Copy Source")
        original_record.external_reference.id = "787878787878787878"

        copied_record = original_record.copy({"name": "Copy Target"})

        self.assertFalse(copied_record.external_reference.id)
        self.assertEqual(original_record.external_ids_count, 1)
        self.assertEqual(copied_record.external_ids_count, 0)

    def test_map_by_bound_external_id_returns_lookup_for_recordset(self) -> None:
        first_record = self._create_fixture("First Bound Map Record")
        second_record = self._create_fixture("Second Bound Map Record")
        first_record.external_reference.id = "888888888888888888"
        second_record.external_reference.id = "999999999999999999"

        mapping = (first_record | second_record).map_by_bound_external_id()

        self.assertEqual(mapping["888888888888888888"], first_record)
        self.assertEqual(mapping["999999999999999999"], second_record)

    def test_fluent_resource_url_uses_runtime_template(self) -> None:
        self._use_test_catalog_urls()
        record = self._create_fixture("URL Record")
        record.external.catalog.product.id = "123456"

        self.assertEqual(
            record.external.catalog.product.url("product_admin"),
            "https://admin.example.test/products/123456",
        )
        self.assertEqual(
            record.external.catalog.product.url("product_store"),
            "https://store.example.test/products/123456",
        )

        self.assertEqual(
            record.external.catalog.product.url("admin"),
            "https://admin.example.test/products/123456",
        )
        self.assertEqual(
            record.external.catalog.product.url("store"),
            "https://store.example.test/products/123456",
        )

    def test_fluent_url_resource_is_inferred_when_omitted(self) -> None:
        legacy_system = self.ExternalSystem.create(
            {
                "name": "Legacy URL System",
                "code": "legacy_urls",
                "url": "https://legacy.example.com",
            }
        )
        self.env["external.system.url"].create(
            {
                "name": "Legacy Admin",
                "code": "admin",
                "system_id": legacy_system.id,
                "resource": "legacy",
                "template": "{base}/legacy/{id}",
                "sequence": 10,
            }
        )

        record = self._create_fixture("Inferred URL Record")
        record.external.legacy_urls.legacy.id = "abc-legacy-id"

        self.assertEqual(
            record.get_external_url("legacy_urls", "admin"),
            "https://legacy.example.com/legacy/abc-legacy-id",
        )

    def test_fluent_resource_url_ignores_archived_external_id(self) -> None:
        self._use_test_catalog_urls()
        record = self._create_fixture("Archived URL Record")
        record.external.catalog.product.id = "654321"

        self.assertEqual(
            record.external.catalog.product.url("admin"),
            "https://admin.example.test/products/654321",
        )

        record.external.catalog.product.active = False

        self.assertIsNone(record.external.catalog.product.id)
        self.assertEqual(record.external.catalog.product.id_any, "654321")
        self.assertIsNone(record.external.catalog.product.url("admin"))
        self.assertIsNone(record.external.catalog.product.url("store"))

    def test_open_external_url_blocked_for_archived_mapping(self) -> None:
        self._use_test_catalog_urls()
        record = self._create_fixture("Archived URL Action Record")
        record.external.catalog.product.id = "999999"

        active_action = record.with_context(
            external_system_code="catalog",
            external_url_kind="admin",
            external_resource="product",
        ).action_open_external_url()

        self.assertEqual(active_action["type"], "ir.actions.act_url")
        self.assertEqual(
            active_action["url"],
            "https://admin.example.test/products/999999",
        )

        record.external.catalog.product.active = False

        blocked_action_result = record.with_context(
            external_system_code="catalog",
            external_url_kind="admin",
            external_resource="product",
        ).action_open_external_url()

        self.assertEqual(blocked_action_result["type"], "ir.actions.client")

        blocked_action: "odoo.values.ir_actions_client" = blocked_action_result
        blocked_params = blocked_action["params"]

        self.assertEqual(blocked_action["type"], "ir.actions.client")
        self.assertEqual(blocked_params.get("type"), "warning")

    def test_fluent_resource_accepts_enum_resource_keys(self) -> None:
        record = self._create_fixture("Enum Record")

        record.external.system(TestSystemCode.CATALOG).resource(
            TestResourceName.PRODUCT
        ).id = "999999"

        self.assertEqual(record.external.catalog.product.id, "999999")

    def test_action_view_external_ids(self) -> None:
        record = self._create_fixture("View Test")
        record.external.sample.default.id = "888888888888888888"

        action = record.action_view_external_ids()

        self.assertEqual(action["type"], "ir.actions.act_window")
        self.assertEqual(action["res_model"], "external.id")
        self.assertIn(("res_model", "=", "external.id.fixture"), action["domain"])
        self.assertIn(("res_id", "=", record.id), action["domain"])
        self.assertEqual(action["context"]["default_res_model"], "external.id.fixture")
        self.assertEqual(action["context"]["default_res_id"], record.id)

    def _racing_external_id_search(self):
        # Hide existing mappings from set_external_id's pre-checks, as if
        # another transaction committed them in between.
        external_id_class = type(self.ExternalId)
        original_search = external_id_class.search
        hidden_calls = {"remaining": 2}

        def racing_search(model, domain, *args, **kwargs):
            if hidden_calls["remaining"]:
                hidden_calls["remaining"] -= 1
                return model.browse()
            return original_search(model, domain, *args, **kwargs)

        return common.patch.object(external_id_class, "search", racing_search)

    def test_set_external_id_reuses_inactive_mapping(self) -> None:
        record = self._create_fixture("Inactive Reuse")
        external_id_record = self.ExternalId.create(
            {
                "res_model": "external.id.fixture",
                "res_id": record.id,
                "system_id": self.sample_system.id,
                "external_id": "stale-id",
                "active": False,
            }
        )

        self.assertTrue(record.set_external_id("sample", "reactivated-id"))

        mappings = self.ExternalId.with_context(active_test=False).search(
            [("res_model", "=", "external.id.fixture"), ("res_id", "=", record.id)]
        )
        self.assertEqual(mappings, external_id_record)
        self.assertTrue(external_id_record.active)
        self.assertEqual(external_id_record.external_id, "reactivated-id")

    def test_get_or_create_rejects_archived_mapping_of_live_record(self) -> None:
        record = self._create_fixture("Archived Live")
        record.external.sample.default.id = "archived-live-id"
        record.external.sample.default.active = False

        with self.assertRaises(ValueError):
            self.FixtureRecord.get_or_create_by_external_id(
                "sample", "archived-live-id", {"name": "Duplicate"}
            )

        self.assertEqual(
            self.FixtureRecord.search_count([("name", "=", "Duplicate")]), 0
        )

    def test_set_external_id_skips_id_owned_by_another_model(self) -> None:
        partner = self.Partner.create({"name": "Owner Partner"})
        self.ExternalId.create(
            {
                "res_model": "res.partner",
                "res_id": partner.id,
                "system_id": self.sample_system.id,
                "external_id": "shared-id",
            }
        )
        record = self._create_fixture("Other Model")

        self.assertFalse(record.set_external_id("sample", "shared-id"))

        mapping = self.ExternalId.search(
            [
                ("external_id", "=", "shared-id"),
                ("system_id", "=", self.sample_system.id),
            ]
        )
        self.assertEqual(
            (mapping.res_model, mapping.res_id), ("res.partner", partner.id)
        )

    def test_set_external_id_moves_id_between_records_of_one_model(self) -> None:
        first_record = self._create_fixture("First Owner")
        second_record = self._create_fixture("Second Owner")
        first_record.set_external_id("sample", "moved-id")
        second_record.set_external_id("sample", "old-second-id")

        self.assertTrue(second_record.set_external_id("sample", "moved-id"))

        self.assertEqual(
            self.FixtureRecord.search_by_external_id("sample", "moved-id"),
            second_record,
        )
        self.assertFalse(first_record.get_external_id_record("sample"))
        self.assertFalse(
            self.ExternalId.with_context(active_test=False).search(
                [("external_id", "=", "old-second-id")]
            )
        )

    def test_set_external_id_recovers_when_same_mapping_appears_concurrently(
        self,
    ) -> None:
        record = self._create_fixture("Concurrent Same")
        record.set_external_id("sample", "race-id")

        with self._racing_external_id_search():
            self.assertTrue(record.set_external_id("sample", "race-id"))

        mappings = self.ExternalId.search([("external_id", "=", "race-id")])
        self.assertEqual(len(mappings), 1)
        self.assertEqual(mappings.res_id, record.id)

    def test_set_external_id_recovers_when_other_record_takes_id_concurrently(
        self,
    ) -> None:
        winner = self._create_fixture("Concurrent Winner")
        winner.set_external_id("sample", "contested-id")
        record = self._create_fixture("Concurrent Loser")

        with self._racing_external_id_search():
            self.assertTrue(record.set_external_id("sample", "contested-id"))

        self.assertEqual(
            self.FixtureRecord.search_by_external_id("sample", "contested-id"), record
        )

    def test_set_external_id_still_raises_format_errors(self) -> None:
        self.sample_system.id_format = r"^\d+$"
        record = self._create_fixture("Bad Format")

        with self.assertRaises(ValidationError):
            record.set_external_id("sample", "not-a-number")
