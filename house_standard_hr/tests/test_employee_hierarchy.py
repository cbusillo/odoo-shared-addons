from lxml import etree
from odoo.tests import TransactionCase
from odoo.tests.common import new_test_user


class TestEmployeeHierarchy(TransactionCase):
    def test_department_cue_is_present_in_each_native_employee_view(self) -> None:
        for model_name, view_ref, group in (
            ("hr.employee", "hr.hr_employee_hierarchy_view", "hr.group_hr_user"),
            ("hr.employee.public", "hr.hr_employee_public_hierarchy_view", "base.group_user"),
        ):
            with self.subTest(model=model_name):
                user = new_test_user(self.env, login=f"hierarchy-{model_name}", groups=group)
                view = self.env[model_name].with_user(user).get_view(view_id=self.env.ref(view_ref).id, view_type="hierarchy")
                card = etree.fromstring(view["arch"]).find(".//t[@t-name='hierarchy-box']")
                self.assertIsNotNone(card)
                department = card.find(".//span[@class='o_house_hierarchy_department']")
                self.assertIsNotNone(department)
