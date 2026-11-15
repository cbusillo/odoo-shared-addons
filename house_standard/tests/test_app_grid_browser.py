import json

from odoo.tests import HttpCase, tagged
from odoo.tests.common import DEFAULT_SUCCESS_SIGNAL

OPEN_FIRST_APP_JS = f"""(async () => {{
    const app = document.querySelector('.o_house_app');
    const name = app.textContent.trim();
    app.click();
    const deadline = Date.now() + 20000;
    while (document.querySelector('.o_menu_brand')?.textContent.trim() !== name) {{
        if (Date.now() > deadline) {{
            throw new Error(`The ${{name}} app did not open from the app grid`);
        }}
        await new Promise((resolve) => setTimeout(resolve, 100));
    }}
    console.log({json.dumps(DEFAULT_SUCCESS_SIGNAL)});
}})()"""


@tagged("-at_install", "post_install")
class TestAppGridBrowser(HttpCase):
    def test_web_client_lands_on_app_grid_and_opens_an_app(self) -> None:
        self.browser_js(
            "/odoo", OPEN_FIRST_APP_JS, ready="Boolean(document.querySelector('.o_house_app_grid .o_house_app'))", login="admin"
        )
