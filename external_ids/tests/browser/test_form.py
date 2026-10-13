import json

from odoo.tests import HttpCase, tagged

from ..fixtures.base import UnitTestCase


@tagged("post_install", "-at_install")
class TestExternalIdFormBrowser(UnitTestCase, HttpCase):
    def test_inherited_form_and_external_ids_open(self) -> None:
        record = self.FixtureRecord.create(
            {"name": "Synthetic identity browser record"}
        )
        system = self.ExternalSystem.create(
            {"name": "Browser fixture", "code": "browser_fixture"}
        )
        identity = "fixture-731"
        record.set_external_id(system.code, identity)
        form = self.env["ir.ui.view"].create(
            {
                "name": "Browser fixture form",
                "model": record._name,
                "type": "form",
                "arch": '<form><sheet><div name="button_box"/><notebook>'
                '<page name="fixture_main" string="Fixture"><field name="name"/></page>'
                "</notebook></sheet></form>",
            }
        )
        self.env["ir.ui.view"].create(
            {
                "name": "Browser inherited page",
                "model": record._name,
                "inherit_id": form.id,
                "arch": '<notebook position="inside"><page name="fixture_inherited" string="Inherited">'
                '<field name="active"/></page></notebook>',
            }
        )
        action = self.env["ir.actions.act_window"].create(
            {
                "name": "Browser identity fixture",
                "res_model": record._name,
                "res_id": record.id,
                "view_mode": "form",
                "view_id": form.id,
            }
        )
        code = """
            (async () => {
                const waitFor = async (selector) => {
                    for (let attempt = 0; attempt < 100; attempt++) {
                        const node = document.querySelector(selector);
                        if (node) return node;
                        await new Promise(resolve => setTimeout(resolve, 100));
                    }
                    throw new Error(`Missing browser element: ${selector}`);
                };
                await waitFor('.o_form_view');
                (await waitFor('[name="fixture_inherited"]')).click();
                await waitFor('.o_field_widget[name="active"]');
                (await waitFor('[name="external_ids"]')).click();
                const list = await waitFor('.o_field_widget[name="external_ids"] .o_list_table');
                if (!list.textContent.includes(IDENTITY)) throw new Error('External identity row missing');
                const button = await waitFor('button[name="action_view_external_ids"]');
                if (!button.textContent.includes('1')) throw new Error('External identity count missing');
                button.click();
                const rows = await waitFor('.o_list_view .o_data_row');
                if (!rows.textContent.includes(IDENTITY)) throw new Error('External identity action row missing');
                console.log('test successful');
            })().catch(error => console.error(error));
        """.replace("IDENTITY", json.dumps(identity))
        self.browser_js(f"/odoo/action-{action.id}", code, login="admin", timeout=90)
