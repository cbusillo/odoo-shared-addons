from odoo.tests import TransactionCase, tagged


@tagged("-at_install", "post_install")
class TestBannerConfiguration(TransactionCase):
    def test_empty_and_false_strings_preserve_enabled_default(self) -> None:
        parameters = self.env["ir.config_parameter"].sudo()
        for value, enabled in (
            (None, True),
            ("", True),
            ("False", False),
            ("0", False),
            ("True", True),
        ):
            with self.subTest(value=value):
                parameters.set_str("environment_banner.enabled", value)
                config = self.env["ir.http"]._get_environment_banner_config()
                self.assertEqual(config["enabled"], enabled)

    def test_configured_hostnames_are_normalized(self) -> None:
        self.env["ir.config_parameter"].sudo().set_str(
            "environment_banner.production_hostnames",
            "EXAMPLE.TEST, other.test\nthird.test",
        )
        config = self.env["ir.http"]._get_environment_banner_config()
        self.assertEqual(
            config["production_hostnames"], ["example.test", "other.test", "third.test"]
        )
