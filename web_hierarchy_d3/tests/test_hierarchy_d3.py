import json

from odoo.tests import HttpCase, tagged
from odoo.tests.common import new_test_user
from odoo.tools import file_open


@tagged("-at_install", "post_install")
class TestHierarchyD3(HttpCase):
    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.reader = new_test_user(cls.env, login="chart-reader")
        cls.category = cls.env["res.partner.category"]
        cls.hierarchy_view = cls.env["ir.ui.view"].create(
            {
                "name": "Synthetic tag hierarchy",
                "model": cls.category._name,
                "arch": """
                    <hierarchy js_class="hierarchy_d3" child_field="child_ids" default_order="name">
                        <field name="name"/>
                        <field name="color" options="{'hierarchy_d3': 'color'}"/>
                        <templates>
                            <t t-name="hierarchy-box"><field name="name"/></t>
                        </templates>
                    </hierarchy>
                """,
            }
        )

        cls.search_view = cls.env["ir.ui.view"].create(
            {
                "name": "Synthetic tag search",
                "model": cls.category._name,
                "arch": """
                    <search>
                        <filter name="limes" string="Only limes" domain="[('name', '=', 'Limes')]"/>
                    </search>
                """,
            }
        )

    def open_chart(self, ids: list[int], check: str, case_data: dict[str, int]) -> None:
        action = self.env["ir.actions.act_window"].create(
            {
                "name": "Synthetic partner tags",
                "res_model": self.category._name,
                "view_mode": "hierarchy,form",
                "search_view_id": self.search_view.id,
                "domain": repr([("id", "in", ids)]),
            }
        )
        self.env["ir.actions.act_window.view"].create(
            {"act_window_id": action.id, "view_mode": "hierarchy", "view_id": self.hierarchy_view.id}
        )
        with file_open("web_hierarchy_d3/tests/chart_checks.js") as script:
            code = f"({script.read()})({json.dumps(check)}, {json.dumps(case_data)});"
        self.browser_js(
            f"/odoo/action-{action.id}",
            code,
            ready="Boolean(document.querySelector('.o_hierarchy_d3_canvas'))",
            login=self.reader.login,
        )

    def test_chart_uses_the_action_domain_and_record_rules(self) -> None:
        root, second, protected, excluded = self.category.create(
            [
                {"name": "Orchard"},
                {"name": "Workshop"},
                {"name": "Restricted synthetic tag"},
                {"name": "Outside the action"},
            ]
        )
        child, detached, inactive = self.category.create(
            [
                {"name": "Limes", "parent_id": root.id},
                {"name": "Accessible branch", "parent_id": protected.id},
                {"name": "Inactive chart tag", "active": False},
            ]
        )
        self.env["ir.access"].create(
            {
                "name": "Hide synthetic restricted tag",
                "model_id": self.env["ir.model"]._get_id(self.category._name),
                "operation": "r",
                "domain": repr([("id", "!=", protected.id)]),
            }
        )
        self.assertFalse(self.category.with_user(self.reader).search([("id", "=", protected.id)]))
        self.open_chart(
            (root | second | child | detached | protected | inactive).ids,
            "behavior",
            {
                "root": root.id,
                "second": second.id,
                "child": child.id,
                "detached": detached.id,
                "protected": protected.id,
                "excluded": excluded.id,
                "inactive": inactive.id,
            },
        )

    def test_chart_reports_truncation_and_stable_order(self) -> None:
        tags = self.category.create([{"name": "Same name"} for _ in range(201)])
        self.open_chart(tags.ids, "limit", {"first": tags[0].id, "last": tags[-1].id})
