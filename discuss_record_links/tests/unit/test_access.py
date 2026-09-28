from contextlib import contextmanager
from unittest.mock import patch

from odoo.exceptions import AccessError
from odoo.tests import HttpCase, TransactionCase, new_test_user
from odoo.tests.common import JsonRpcException

from ...controllers.main import DiscussRecordLinks
from ..common_imports import common

REQUEST_PATH = "odoo.addons.discuss_record_links.controllers.main.request"


def _create_config(env, *, prefix: str, model_name: str, search_field_names: tuple[str, ...], template: str) -> None:
    ir_model = env["ir.model"]._get(model_name)
    # Only this test's config may label the model.
    env["discuss.record.link.config"].search([("model_id", "=", ir_model.id)]).active = False
    search_fields = env["ir.model.fields"].search([("model_id", "=", ir_model.id), ("name", "in", search_field_names)])
    env["discuss.record.link.config"].create(
        {
            "active": True,
            "prefix": prefix,
            "label": prefix,
            "model_id": ir_model.id,
            "search_field_ids": [(6, 0, search_fields.ids)],
            "display_template": template,
            "limit": 20,
        }
    )


@common.tagged(*common.UNIT_TAGS)
class TestRouteAccess(TransactionCase):
    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.main_company = cls.env.company
        cls.other_company = cls.env["res.company"].create({"name": "DRL Other Company"})
        _create_config(
            cls.env,
            prefix="tacc",
            model_name="product.product",
            search_field_names=("name",),
            template="{{ name }} / {{ default_code }}",
        )
        product_model = cls.env["product.product"].with_context(skip_sku_check=True)
        cls.visible_product = product_model.create(
            {"name": "Drlaccess Visible", "default_code": "DRLV", "company_id": cls.main_company.id}
        )
        cls.hidden_product = product_model.create(
            {"name": "Drlaccess Hidden", "default_code": "DRLH", "company_id": cls.other_company.id}
        )
        cls.internal_user = new_test_user(
            cls.env,
            login="drl_internal",
            groups="base.group_user",
            company_id=cls.main_company.id,
            company_ids=[(6, 0, [cls.main_company.id])],
        )
        cls.portal_user = new_test_user(cls.env, login="drl_portal", groups="base.group_portal")

    @contextmanager
    def _as(self, user):
        fake_request = type("_Req", (), {})()
        fake_request.env = self.env(user=user)
        with patch(REQUEST_PATH, fake_request):
            yield DiscussRecordLinks()

    def test_portal_user_is_refused_labels(self) -> None:
        with self._as(self.portal_user) as controller, self.assertRaises(AccessError):
            controller.labels(targets=[{"model": "product.product", "id": self.visible_product.id}])

    def test_portal_user_is_refused_search(self) -> None:
        with self._as(self.portal_user) as controller, self.assertRaises(AccessError):
            controller.search(term="tacc Drlaccess")

    def test_labels_follow_record_rules(self) -> None:
        missing_id = self.env["product.product"].search([], order="id desc", limit=1).id + 1000
        targets = [
            {"model": "product.product", "id": self.visible_product.id},
            {"model": "product.product", "id": self.hidden_product.id},
            {"model": "product.product", "id": missing_id},
        ]
        with self._as(self.internal_user) as controller:
            rows = controller.labels(targets=targets)

        self.assertEqual(
            rows,
            [{"model": "product.product", "id": self.visible_product.id, "label": "Drlaccess Visible / DRLV"}],
        )

    def test_search_follows_record_rules(self) -> None:
        with self._as(self.internal_user) as controller:
            suggestions = controller.search(term="tacc Drlaccess")["suggestions"]

        self.assertEqual({s["id"] for s in suggestions}, {self.visible_product.id})
        self.assertEqual(suggestions[0]["label"], "Drlaccess Visible / DRLV")

    def test_labels_refuse_unconfigured_models(self) -> None:
        partner = self.env["res.partner"].create({"name": "Drlaccess Partner"})
        targets = [
            {"model": "res.partner", "id": partner.id},
            {"model": "no.such.model", "id": 1},
            {"model": "product.product", "id": "not-an-id"},
        ]
        with self._as(self.internal_user) as controller:
            self.assertEqual(controller.labels(targets=targets), [])

    def test_configured_model_without_read_access_is_skipped(self) -> None:
        # A configured model the user has no ACL for yields nothing and does not
        # fail the response for the other configured models.
        _create_config(
            self.env,
            prefix="tcfg",
            model_name="ir.config_parameter",
            search_field_names=("key",),
            template="{{ key }}",
        )
        parameter = self.env["ir.config_parameter"].create({"key": "drlaccess.probe", "value": "x"})
        with self._as(self.internal_user) as controller:
            labels = controller.labels(
                targets=[
                    {"model": "ir.config_parameter", "id": parameter.id},
                    {"model": "product.product", "id": self.visible_product.id},
                ]
            )
            suggestions = controller.search(term="drlaccess")["suggestions"]

        self.assertEqual([(r["model"], r["id"]) for r in labels], [("product.product", self.visible_product.id)])
        self.assertEqual({(s["model"], s["id"]) for s in suggestions}, {("product.product", self.visible_product.id)})


@common.tagged(*common.UNIT_TAGS)
class TestRouteAccessHttp(HttpCase):
    """Exercise the real JSON-RPC routes with real sessions."""

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        _create_config(
            cls.env,
            prefix="thttp",
            model_name="product.product",
            search_field_names=("name",),
            template="{{ name }} / {{ default_code }}",
        )
        cls.product = (
            cls.env["product.product"]
            .with_context(skip_sku_check=True)
            .create({"name": "Drlhttp Widget", "default_code": "DRLW"})
        )
        new_test_user(cls.env, login="drl_http_internal", password="drl_http_internal", groups="base.group_user")
        new_test_user(cls.env, login="drl_http_portal", password="drl_http_portal", groups="base.group_portal")

    def test_portal_session_is_refused(self) -> None:
        self.authenticate("drl_http_portal", "drl_http_portal")
        with self.assertRaises(JsonRpcException):
            self.make_jsonrpc_request(
                "/discuss_record_links/labels", {"targets": [{"model": "product.product", "id": self.product.id}]}
            )
        with self.assertRaises(JsonRpcException):
            self.make_jsonrpc_request("/discuss_record_links/search", {"term": "thttp Drlhttp"})

    def test_internal_session_gets_labels_and_suggestions(self) -> None:
        self.authenticate("drl_http_internal", "drl_http_internal")
        labels = self.make_jsonrpc_request(
            "/discuss_record_links/labels", {"targets": [{"model": "product.product", "id": self.product.id}]}
        )
        suggestions = self.make_jsonrpc_request("/discuss_record_links/search", {"term": "thttp Drlhttp"})["suggestions"]

        self.assertEqual(labels, [{"model": "product.product", "id": self.product.id, "label": "Drlhttp Widget / DRLW"}])
        self.assertEqual([s["id"] for s in suggestions], [self.product.id])
