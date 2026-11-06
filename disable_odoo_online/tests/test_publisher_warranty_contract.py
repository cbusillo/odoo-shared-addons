from unittest.mock import patch

from odoo.tests import tagged
from odoo.tests.common import TransactionCase
from requests import Session


@tagged("-at_install", "post_install")
class TestPublisherWarrantyContract(TransactionCase):
    def test_update_notification_stays_offline(self) -> None:
        for cron_mode in (False, True):
            with (
                self.subTest(cron_mode=cron_mode),
                patch.object(Session, "request", side_effect=AssertionError("Publisher warranty must stay offline")) as request,
            ):
                result = self.env["publisher_warranty.contract"].update_notification(cron_mode=cron_mode)
                self.assertTrue(result)
                request.assert_not_called()
