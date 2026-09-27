from .common_imports import common


@common.tagged(*common.UNIT_TAGS)
class TestEmployeePerfConcurrency(common.TransactionCase):
    # noinspection PyPep8Naming
    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.Employee = cls.env["hr.employee"]

    def test_bulk_write(self) -> None:
        employees = self.Employee.create([{"first_name": f"First{i}", "last_name": f"Last{i}"} for i in range(64)])
        employees.write({"nick_name": "Bulk"})
        for employee in employees:
            self.assertEqual(employee.nick_name, "Bulk")
