from .common_imports import common


@common.tagged(*common.UNIT_TAGS)
class TestNameSettings(common.TransactionCase):
    # noinspection PyPep8Naming
    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.Employee = cls.env["hr.employee"]
        cls.Settings = cls.env["res.config.settings"]
        cls.ICP = cls.env["ir.config_parameter"].sudo()

    def setUp(self) -> None:
        super().setUp()
        self.ICP.set_param("user_name_extended.format", "western")
        self.ICP.set_param("user_name_extended.custom_pattern", False)

    def test_settings_format_updates_icp_and_affects_name(self) -> None:
        emp = self.Employee.create({"first_name": "Wei", "last_name": "Zhang", "name_format": ""})
        self.assertEqual(emp.name, "Wei Zhang")

        settings = self.Settings.create({"user_name_format": "asian"})
        settings.execute()

        fmt = (self.ICP.get_param("user_name_extended.format") or "").strip()
        self.assertEqual(fmt, "asian")

        self.Employee._action_recompute_names()
        self.assertEqual(emp.name, "Zhang Wei")

    def test_settings_custom_pattern_applies(self) -> None:
        emp = self.Employee.create({"first_name": "Robert", "last_name": "Johnson", "nick_name": "Bob", "name_format": ""})

        settings = self.Settings.create(
            {
                "user_name_format": "custom",
                "user_name_custom_pattern": "{last_name}, {first_name} ({nickname})",
            }
        )
        settings.execute()

        fmt = (self.ICP.get_param("user_name_extended.format") or "").strip()
        pat = (self.ICP.get_param("user_name_extended.custom_pattern") or "").strip()
        self.assertEqual(fmt, "custom")
        self.assertEqual(pat, settings.user_name_custom_pattern)

        self.Employee._action_recompute_names()
        self.assertEqual(emp.name, "Johnson, Robert (Bob)")

    def test_recompute_preserves_saved_and_explicit_formats(self) -> None:
        for initial_format, changed_format in (("western", "asian"), ("asian", "western")):
            with self.subTest(initial_format=initial_format):
                self.ICP.set_param("user_name_extended.format", initial_format)
                saved_default = self.Employee.create({"first_name": "Wei", "last_name": "Zhang"})
                explicit = self.Employee.create(
                    {"first_name": "Wei", "last_name": "Zhang", "name_format": initial_format}
                )
                system_default = self.Employee.create(
                    {"first_name": "Wei", "last_name": "Zhang", "name_format": ""}
                )
                initial_name = "Wei Zhang" if initial_format == "western" else "Zhang Wei"
                changed_name = "Wei Zhang" if changed_format == "western" else "Zhang Wei"
                self.assertEqual(saved_default.name_format, initial_format)
                self.assertEqual((saved_default.name, explicit.name, system_default.name), (initial_name,) * 3)

                self.Settings.create({"user_name_format": changed_format}).execute()
                # Settings changes alone do not retroactively change stored names.
                self.assertEqual(system_default.name, initial_name)
                self.Employee._action_recompute_names()

                self.assertEqual(system_default.name, changed_name)
                self.assertEqual((saved_default.name, explicit.name), (initial_name,) * 2)
                self.assertEqual((saved_default.name_format, explicit.name_format), (initial_format,) * 2)
                for employee in saved_default | explicit | system_default:
                    self.assertEqual(employee.resource_id.name, employee.name)
