from test_support.tests.fixtures.unit_case import AdminContextUnitTestCase

from ..common_imports import common


@common.tagged(*common.UNIT_TAGS)
class UnitTestCase(AdminContextUnitTestCase):
    default_test_context = common.DEFAULT_TEST_CONTEXT
    model_aliases = {
        "Settings": "launchplane.settings",
    }

    @property
    def Settings(self) -> "odoo.model.launchplane_settings":
        return self.env["launchplane.settings"]

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.ConfigParameter = cls.env["ir.config_parameter"].sudo()
