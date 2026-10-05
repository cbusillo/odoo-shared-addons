from lxml import etree
from odoo.tools.safe_eval import safe_eval

from ...models.external_id_mixin import ExternalIdMixin
from ..common_imports import common
from ..fixtures.base import UnitTestCase


class FakeExternalIdsUiModel:
    _name = "external.id.fixture"
    _external_ids_auto_ui = True
    _fields = {"external_ids": object()}
    _inject_external_ids_button = ExternalIdMixin.__dict__["_inject_external_ids_button"]
    _inject_external_ids_page = ExternalIdMixin.__dict__["_inject_external_ids_page"]
    _build_external_ids_page_arch = ExternalIdMixin.__dict__["_build_external_ids_page_arch"]
    _inject_external_ids_form_ui = ExternalIdMixin.__dict__["_inject_external_ids_form_ui"]
    inject_external_ids_button = ExternalIdMixin.__dict__["_inject_external_ids_button"]
    inject_external_ids_page = ExternalIdMixin.__dict__["_inject_external_ids_page"]
    build_external_ids_page_arch = ExternalIdMixin.__dict__["_build_external_ids_page_arch"]
    inject_external_ids_form_ui = ExternalIdMixin.__dict__["_inject_external_ids_form_ui"]


@common.tagged(*common.UNIT_TAGS)
class TestViewsLoad(UnitTestCase):
    def test_inject_external_ids_button_and_page(self) -> None:
        view_definition = {
            "arch": """
                <form>
                    <sheet>
                        <div name="button_box"/>
                        <notebook>
                            <page string="Main" name="main"/>
                        </notebook>
                    </sheet>
                </form>
            """
        }

        injected = FakeExternalIdsUiModel.inject_external_ids_form_ui(view_definition, "form")
        architecture = etree.fromstring(injected["arch"].encode())
        buttons = architecture.xpath(".//div[@name='button_box']/button[@name='action_view_external_ids']")
        self.assertEqual(len(buttons), 1)
        self.assertEqual(buttons[0].get("type"), "object")
        self.assertEqual(len(buttons[0].xpath("./field[@name='external_ids_count']")), 1)
        fields = architecture.xpath(".//sheet/notebook/page[@name='external_ids']/field[@name='external_ids']")
        self.assertEqual(len(fields), 1)
        record_id = 731
        context = safe_eval(fields[0].get("context"), {"id": record_id})
        self.assertEqual(context["default_res_model"], FakeExternalIdsUiModel._name)
        self.assertEqual(context["default_res_id"], record_id)
        self.assertEqual(
            safe_eval(fields[0].get("domain")), [("res_model", "=", FakeExternalIdsUiModel._name)]
        )

    def test_inject_external_ids_page_creates_notebook_when_missing(self) -> None:
        view_definition = {
            "arch": """
                <form>
                    <sheet>
                        <div name="button_box"/>
                        <group/>
                    </sheet>
                </form>
            """
        }

        injected = FakeExternalIdsUiModel.inject_external_ids_form_ui(view_definition, "form")

        architecture = etree.fromstring(injected["arch"].encode())
        self.assertEqual(len(architecture.xpath(".//sheet/notebook/page[@name='external_ids']")), 1)

    def test_inject_external_ids_ui_is_idempotent(self) -> None:
        view_definition = {
            "arch": """
                <form>
                    <sheet>
                        <div name="button_box">
                            <button name="action_view_external_ids" type="object"/>
                        </div>
                        <notebook>
                            <page string="External IDs" name="external_ids"/>
                        </notebook>
                    </sheet>
                </form>
            """
        }

        injected = FakeExternalIdsUiModel.inject_external_ids_form_ui(view_definition, "form")

        architecture = etree.fromstring(injected["arch"].encode())
        self.assertEqual(len(architecture.xpath(".//button[@name='action_view_external_ids']")), 1)
        self.assertEqual(len(architecture.xpath(".//page[@name='external_ids']")), 1)
