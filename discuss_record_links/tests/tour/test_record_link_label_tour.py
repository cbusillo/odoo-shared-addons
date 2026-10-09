from ..common_imports import common
from ..fixtures.base import TourTestCase


@common.tagged(*common.TOUR_TAGS)
class TestRecordLinkLabelTour(TourTestCase):
    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        product_record = cls.ensure_tour_product(default_code="1004", name="Widget E2E")
        config = cls.ensure_record_link_config(
            prefix="tprolabel",
            display_template="OSA {{ name }} / {{ default_code }}",
        )
        # Keep the fixture's template authoritative regardless of config order.
        cls.env["discuss.record.link.config"].search(
            [("model_id", "=", config.model_id.id), ("id", "!=", config.id)]
        ).write({"active": False})
        expected_label = config.display_template.replace(
            "{{ default_code }}",
            product_record.default_code,
        ).replace("{{ name }}", product_record.name)
        cls.set_config_parameter("drl_label_product_id", product_record.id)
        cls.set_config_parameter("drl_label_expected_label", expected_label)
        cls._drl_active_id = cls.ensure_discuss_channel_active_id()

    def test_record_link_label_tour(self) -> None:
        start_url = f"/odoo/action-mail.action_discuss?active_id={self._drl_active_id}"
        self.start_tour(
            start_url,
            "drl_record_link_label",
            login=self._get_test_login(),
            timeout=300,
        )
