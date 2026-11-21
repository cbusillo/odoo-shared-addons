from lxml import etree
from odoo.tests import TransactionCase
from odoo.tests.common import new_test_user


class TestEmployeeHierarchy(TransactionCase):
    def test_department_cue_is_present_in_each_native_employee_view(self) -> None:
        officer = new_test_user(self.env, login="hierarchy-officer", groups="hr.group_hr_user")
        staff = new_test_user(self.env, login="hierarchy-staff", groups="base.group_user")
        officer_view_id = self.env.ref("hr.hr_employee_hierarchy_view").id
        staff_view_id = self.env.ref("hr.hr_employee_public_hierarchy_view").id
        views = (
            self.env["hr.employee"].with_user(officer).get_view(officer_view_id, "hierarchy"),
            self.env["hr.employee.public"].with_user(staff).get_view(staff_view_id, "hierarchy"),
        )
        for view in views:
            card = etree.fromstring(view["arch"]).find(".//t[@t-name='hierarchy-box']")
            self.assertIsNotNone(card)
            self.assertIsNotNone(card.find(".//span[@class='o_house_hierarchy_department']"))
