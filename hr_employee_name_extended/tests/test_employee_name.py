from odoo.exceptions import ValidationError

from .common_imports import common


@common.tagged(*common.UNIT_TAGS)
class TestEmployeeName(common.TransactionCase):
    # noinspection PyPep8Naming
    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.Employee = cls.env["hr.employee"]
        cls.ICP = cls.env["ir.config_parameter"].sudo()

    def test_create_and_defaults(self) -> None:
        emp = self.Employee.create({"first_name": "John", "last_name": "Doe"})
        self.assertEqual(emp.nick_name, "John")
        self.assertEqual(emp.name, "John Doe")
        self.assertEqual(emp.display_name, "John Doe")

    def test_part_write_updates_name_and_resource(self) -> None:
        emp = self.Employee.create({"first_name": "John", "last_name": "Doe"})
        self.assertEqual(emp.resource_id.name, emp.name)
        emp.write({"first_name": "Jack"})
        self.assertEqual(emp.name, "Jack Doe")
        self.assertEqual(emp.resource_id.name, "Jack Doe")

    def test_display_with_nickname(self) -> None:
        emp = self.Employee.create({"first_name": "William", "last_name": "Gates", "nick_name": "Bill"})
        self.assertEqual(emp.display_name, "Bill (William Gates)")

    def test_validation_spaces(self) -> None:
        with self.assertRaises(ValidationError):
            self.Employee.create({"first_name": "  John  ", "last_name": "Doe"})

    def test_name_search(self) -> None:
        emp = self.Employee.create({"first_name": "Alice", "last_name": "Smith", "nick_name": "Ally"})
        ids = [rid for rid, _ in self.Employee.name_search("Ally")]
        self.assertIn(emp.id, ids)

    def test_inverse_on_name_write(self) -> None:
        self.ICP.set_param("user_name_extended.format", "asian")
        emp = self.Employee.create({"first_name": "Wei", "last_name": "Zhang"})
        emp.name = "Li Wei"
        emp.invalidate_recordset(["first_name", "last_name", "name"])
        self.assertEqual(emp.first_name, "Wei")
        self.assertEqual(emp.last_name, "Li")
        self.assertEqual(emp.name, "Li Wei")

    def test_external_partner_user_changes_do_not_break(self) -> None:
        partner = self.env["res.partner"].create({"name": "Partner A"})
        user = self.env["res.users"].create({"name": "User A", "login": "u@example.com", "partner_id": partner.id})
        emp = self.Employee.create({"first_name": "Jane", "last_name": "Doe", "user_id": user.id, "work_contact_id": partner.id})
        partner.name = "Changed Partner"
        user.name = "Changed User"
        emp.invalidate_recordset(["first_name", "last_name", "name"])
        self.assertEqual(emp.first_name, "Jane")
        self.assertEqual(emp.last_name, "Doe")

    def test_opt_in_sync_via_context(self) -> None:
        partner = self.env["res.partner"].create({"name": "Partner B"})
        emp = self.Employee.create({"first_name": "Carl", "last_name": "Sagan", "work_contact_id": partner.id})
        partner.with_context(allow_employee_sync=True).write({"name": "Sagan Carl"})
        emp.invalidate_recordset(["first_name", "last_name", "name"])
        self.ICP.set_param("user_name_extended.format", "asian")
        partner.with_context(allow_employee_sync=True).write({"name": "Sagan Carl"})
        emp.invalidate_recordset(["first_name", "last_name", "name"])
        self.assertEqual(emp.first_name, "Carl")
        self.assertEqual(emp.last_name, "Sagan")

    def test_create_from_name_only_splits_parts(self) -> None:
        emp = self.Employee.create({"name": "Mary Major"})
        self.assertEqual((emp.first_name, emp.last_name, emp.nick_name), ("Mary", "Major", "Mary"))
        self.assertEqual(emp.name, "Mary Major")

    def test_create_from_name_only_respects_asian_format(self) -> None:
        self.ICP.set_param("user_name_extended.format", "asian")
        emp = self.Employee.create({"name": "Zhang Wei"})
        self.assertEqual((emp.first_name, emp.last_name), ("Wei", "Zhang"))

    def test_create_from_single_word_name(self) -> None:
        emp = self.Employee.create({"name": "Cher"})
        self.assertEqual(emp.first_name, "Cher")
        self.assertFalse(emp.last_name)

    def test_create_without_any_name_is_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            self.Employee.create({"name": "   "})

    def test_user_create_employee_action(self) -> None:
        user = self.env["res.users"].create({"name": "Pat Doe", "login": "pat.doe@example.com"})
        user.action_create_employee()
        self.assertEqual((user.employee_ids.first_name, user.employee_ids.last_name), ("Pat", "Doe"))

    def test_user_created_with_employee(self) -> None:
        user = self.env["res.users"].create({"name": "Sam Roe", "login": "sam.roe@example.com", "create_employee": True})
        self.assertEqual((user.employee_ids.first_name, user.employee_ids.last_name), ("Sam", "Roe"))

    def test_bulk_part_write_recomposes_each_name(self) -> None:
        employees = self.Employee.create([{"first_name": f"First{i}", "last_name": f"Last{i}"} for i in range(64)])

        employees.write({"last_name": "Bulk"})

        for index, employee in enumerate(employees):
            self.assertEqual(employee.name, f"First{index} Bulk")
            self.assertEqual(employee.resource_id.name, f"First{index} Bulk")
