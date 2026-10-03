from odoo.orm import model_classes
from odoo.tests import TransactionCase

from .record import ExternalIdFixture

from ..common_imports import common


@common.tagged(*common.UNIT_TAGS)
class UnitTestCase(TransactionCase):
    default_test_context = common.DEFAULT_TEST_CONTEXT

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, **cls.default_test_context))
        cls.addClassCleanup(cls._remove_fixture_model)
        model_classes.add_to_registry(cls.registry, ExternalIdFixture)
        cls.registry._setup_models__(cls.cr, ["external.id.fixture"])
        cls.registry.init_models(cls.cr, ["external.id.fixture"], {"module": "external_ids"})

    @classmethod
    def _remove_fixture_model(cls) -> None:
        for parent in ("external.id.mixin", "base"):
            cls.registry[parent]._inherit_children.discard("external.id.fixture")
        cls.registry.models.pop("external.id.fixture", None)
        cls.registry._setup_models__(cls.cr)

    @property
    def ExternalSystem(self) -> "odoo.model.external_system":
        return self.env["external.system"]

    @property
    def ExternalId(self) -> "odoo.model.external_id":
        return self.env["external.id"]

    @property
    def FixtureRecord(self) -> "odoo.model.external_id_fixture":
        return self.env["external.id.fixture"]

    @property
    def Partner(self) -> "odoo.model.res_partner":
        return self.env["res.partner"]
