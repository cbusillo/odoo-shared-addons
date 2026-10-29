from unittest.mock import patch

from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged

from ..models import routing


@tagged("post_install", "-at_install")
class TestConfiguration(TransactionCase):
    def test_missing_native_parameter_stops_before_client_creation(self) -> None:
        self.env["ir.config_parameter"].sudo().set_str("printnode.api_key", "")
        with patch.object(routing, "PrintNodeClient") as client:
            with self.assertRaises(UserError):
                self.env["printnode.routing"]._client()
            client.assert_not_called()

    def test_native_parameter_value_reaches_client_without_network_access(self) -> None:
        sentinel = "inert-synthetic-printnode-value"
        self.env["ir.config_parameter"].sudo().set_str("printnode.api_key", sentinel)
        with patch.object(routing, "PrintNodeClient") as client:
            result = self.env["printnode.routing"]._client()
            client.assert_called_once_with(sentinel)
            self.assertIs(result, client.return_value)
