from unittest.mock import patch

from lxml import etree

from ..common_imports import common
from ..fixtures.base import UnitTestCase


@common.tagged(*common.UNIT_TAGS)
class TestViewMetadata(UnitTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.form = self.env["ir.ui.view"].create(
            {
                "name": "External identity metadata fixture",
                "model": self.FixtureRecord._name,
                "type": "form",
                "arch": '<form><sheet><div name="button_box"/><notebook>'
                '<page name="fixture_main"><field name="name"/></page>'
                "</notebook></sheet></form>",
            }
        )
        self.env["ir.ui.view"].create(
            {
                "name": "Inherited fixture page",
                "model": self.FixtureRecord._name,
                "inherit_id": self.form.id,
                "arch": '<notebook position="inside"><page name="fixture_inherited">'
                '<field name="active"/></page></notebook>',
            }
        )

    def test_form_fields_and_subviews_have_client_metadata(self) -> None:
        for _ in range(2):
            result = self.FixtureRecord.get_views([(self.form.id, "form")])
            arch = etree.fromstring(result["views"]["form"]["arch"].encode())
            fields = result["models"][self.FixtureRecord._name]["fields"]
            for field in arch.xpath(".//field[not(ancestor::field)]"):
                self.assertIn(field.get("name"), fields)
            relation = fields["external_ids"]["relation"]
            child_fields = result["models"][relation]["fields"]
            for field in arch.xpath(".//field[@name='external_ids']//field"):
                self.assertIn(field.get("name"), child_fields)
            self.assertEqual(
                fields["external_ids_count"]["type"],
                self.FixtureRecord._fields["external_ids_count"].type,
            )
            self.assertEqual(len(arch.xpath(".//page[@name='fixture_inherited']")), 1)
            self.assertEqual(len(arch.xpath(".//page[@name='external_ids']")), 1)
            self.assertEqual(
                len(arch.xpath(".//button[@name='action_view_external_ids']")), 1
            )

    def test_opt_out_keeps_inherited_pages_without_external_ui(self) -> None:
        with patch.object(type(self.FixtureRecord), "_external_ids_auto_ui", False):
            self.env.registry.clear_cache()
            result = self.FixtureRecord.get_views([(self.form.id, "form")])
            arch = etree.fromstring(result["views"]["form"]["arch"].encode())
            self.assertEqual(len(arch.xpath(".//page[@name='fixture_inherited']")), 1)
            self.assertFalse(
                arch.xpath(
                    ".//field[@name='external_ids' or @name='external_ids_count']"
                )
            )
        self.env.registry.clear_cache()

    def test_non_form_view_is_unchanged(self) -> None:
        view = self.env["ir.ui.view"].create(
            {
                "name": "External identity list fixture",
                "model": self.FixtureRecord._name,
                "type": "list",
                "arch": '<list><field name="name"/></list>',
            }
        )
        result = self.FixtureRecord.get_views([(view.id, "list")])
        arch = etree.fromstring(result["views"]["list"]["arch"].encode())
        self.assertFalse(
            arch.xpath(".//field[@name='external_ids' or @name='external_ids_count']")
        )
