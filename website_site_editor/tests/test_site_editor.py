import base64
from io import BytesIO
from typing import Any

from odoo import Command
from odoo.exceptions import AccessError
from odoo.tests import HttpCase, tagged
from PIL import Image


@tagged("-at_install", "post_install")
class TestSiteEditor(HttpCase):
    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.first_site = cls.env["website"].search([], limit=1)
        cls.second_site = cls.env["website"].create({"name": "Pebble Grove"})
        cls.first_editor, cls.second_editor = (
            cls.env["res.users"]
            .with_context(no_reset_password=True)
            .create(
                [
                    {
                        "name": login.title(),
                        "login": login,
                        "password": login,
                        "group_ids": [Command.set([cls.env.ref("website_site_editor.group_editor").id])],
                    }
                    for login in ("fern", "moss")
                ]
            )
        )
        cls.first_site.site_editor_ids = cls.first_editor
        cls.second_site.site_editor_ids = cls.second_editor
        cls.pages = cls.env["website.page"]
        for site, content in ((cls.first_site, "Amber leaf"), (cls.second_site, "Silver leaf")):
            view = cls.env["ir.ui.view"].create(
                {
                    "name": "Garden notebook",
                    "key": "site_editor_test.garden",
                    "website_id": site.id,
                    "type": "qweb",
                    "arch": '<t t-name="site_editor_test.garden"><t t-call="website.layout"><div id="wrap"><h2 id="garden-heading">Garden notebook</h2><t t-call="website_site_editor.page_body"/></div></t></t>',
                }
            )
            cls.pages |= cls.env["website.page"].create(
                {
                    "view_id": view.id,
                    "url": "/garden-notebook",
                    "is_published": True,
                    "site_editor_body_enabled": True,
                    "site_editor_body": f"<p>{content}</p>",
                }
            )
        cls.first_page, cls.second_page = cls.pages
        cls.preview = cls.first_site.get_client_action_url("/garden-notebook")

    def test_builder_saves_body_without_changing_template(self) -> None:
        self.assertIn("Amber leaf", self.url_open("/garden-notebook").text)
        template = self.env.ref("website_site_editor.page_body")
        originals = (template | self.pages.view_id).mapped("arch_db")
        self.start_tour(self.preview, "site_editor_text", login=self.first_editor.login)
        self.start_tour(self.preview, "site_editor_block", login=self.first_editor.login)
        self.pages.invalidate_recordset()
        self.assertIn("Golden fern", self.first_page.site_editor_body)
        self.assertIn("s_text_block", self.first_page.site_editor_body)
        self.assertEqual(self.second_page.site_editor_body, "<p>Silver leaf</p>")
        self.assertEqual((template | self.pages.view_id).mapped("arch_db"), originals)
        self.assertFalse(self.env["ir.ui.view"].search_count([("key", "=", template.key), ("website_id", "!=", False)]))
        self.authenticate(None, None)
        response = self.url_open("/garden-notebook")
        self.assertEqual(response.status_code, 200)
        self.assertIn("Golden fern", response.text)
        self.assertNotIn('data-editable="1"', response.text)

    def test_builder_moves_and_removes_blocks(self) -> None:
        self.first_page.site_editor_body = "".join(
            f'<section class="s_text_block garden-{label}" data-snippet="s_text_block" data-name="Text"><div class="container"><p>{label} ferns</p></div></section>'
            for label in ("one", "two", "three")
        )
        self.start_tour(self.preview, "site_editor_arrange", login=self.first_editor.login)
        self.first_page.invalidate_recordset()
        body = self.first_page.site_editor_body
        self.assertLess(body.index("two ferns"), body.index("one ferns"))
        self.assertNotIn("three ferns", body)

    def test_unassigned_preview_has_no_edit_control(self) -> None:
        self.start_tour(self.preview, "site_editor_unassigned", login=self.second_editor.login)

    def test_rpc_checks_each_assigned_site(self) -> None:
        for editor, own, other in (
            (self.first_editor, self.first_page, self.second_page),
            (self.second_editor, self.second_page, self.first_page),
        ):
            self.authenticate(editor.login, editor.login)
            own_value = f"<p>{editor.login} garden</p>"
            other_value = other.site_editor_body
            self.assertTrue(self._rpc_write(own, {"site_editor_body": own_value})["result"])
            self.assertEqual(
                self._rpc_write(other, {"site_editor_body": own_value})["error"]["data"]["name"], "odoo.exceptions.AccessError"
            )
            self.pages.invalidate_recordset()
            self.assertEqual(own.site_editor_body, own_value)
            self.assertEqual(other.site_editor_body, other_value)

    def _rpc_write(self, page: "odoo.model.website_page", values: dict[str, Any]) -> dict[str, Any]:
        response = self.url_open(
            "/web/dataset/call_kw/website.page.write",
            json={
                "jsonrpc": "2.0",
                "method": "call",
                "id": 1,
                "params": {"model": page._name, "method": "write", "args": [[page.id], values], "kwargs": {}},
            },
        )
        self.assertEqual(response.status_code, 200)
        return response.json()

    def test_page_url_menu_and_homepage_follow_the_assignment(self) -> None:
        for page, editor, other in (
            (self.first_page, self.first_editor, self.second_editor),
            (self.second_page, self.second_editor, self.first_editor),
        ):
            site = page.website_id
            site.with_user(editor).write({"homepage_url": page.url})
            page.with_user(editor).with_context(website_id=site.id, lang=site.default_lang_id.code).write(
                {"url": "/ferns", "website_indexed": False}
            )
            self.assertEqual(site.homepage_url, page.url)
            self.assertEqual(page.url, "/ferns")
            self.assertFalse(page.website_indexed)
            menus = self.env["website.menu"].with_user(editor)
            entry = {
                "id": "new-fern",
                "parent_id": site.menu_id.id,
                "name": "Ferns",
                "url": page.url,
                "new_window": False,
                "sequence": 2,
                "is_mega_menu": False,
            }
            menus.save(site.id, {"data": [entry]})
            menu = menus.browse(entry["id"])
            self.assertEqual(menu.website_id, site)
            self.assertEqual(menu.page_id, page)
            with self.assertRaises(AccessError):
                menu.with_user(other).write({"name": "Different name"})
            with self.assertRaises(AccessError):
                page.with_user(other).write({"url": "/unassigned"})
            with self.assertRaises(AccessError):
                site.with_user(other).sudo().write({"homepage_url": "/unassigned"})
            self.assertEqual(site.homepage_url, "/ferns")
            menus.save(site.id, {"data": [], "to_delete": [menu.id]})
            self.assertFalse(menu.exists())

    def test_menu_tree_and_record_reads_follow_page_visibility(self) -> None:
        site, page = self.second_site, self.second_page
        admin = self.env.ref("base.user_admin")
        menus = self.env["website.menu"].with_user(admin)
        entry = {"id": "new-notebook", "name": "Notebook", "url": page.url, "parent_id": site.menu_id.id}
        menus.save(site.id, {"data": [entry]})
        menu = menus.browse(entry["id"])
        self.assertEqual(menu.page_id, page)
        self.assertFalse(menu.group_ids)

        for values, visible_elsewhere in (
            ({}, True),
            ({"is_published": False}, False),
            (
                {
                    "is_published": True,
                    "visibility": "restricted_group",
                    "group_ids": [Command.set([self.env.ref("base.group_system").id])],
                },
                False,
            ),
            ({"group_ids": [Command.set([self.env.ref("base.group_user").id])]}, True),
            ({"visibility": "password"}, False),
        ):
            if values:
                page.with_user(admin).write(values)
            for user, visible in ((self.first_editor, visible_elsewhere), (self.second_editor, True), (admin, True)):
                with self.subTest(values=values, user=user.login):
                    user_menu = menu.with_user(user)
                    children = user_menu.get_tree(site.id)["children"]
                    self.assertEqual(menu.id in {child["fields"]["id"] for child in children}, visible)
                    if visible:
                        self.assertEqual(user_menu.read(["name", "url"])[0]["url"], page.url)
                    else:
                        with self.assertRaises(AccessError):
                            user_menu.read(["name", "url"])

    def test_template_global_settings_and_site_binding_stay_admin_owned(self) -> None:
        editor = self.first_editor
        self.assertFalse(self.env["ir.ui.view"].with_user(editor).has_access("write"))
        self.assertFalse(self.first_page.view_id.with_user(editor).has_access("write"))
        self.first_page.site_editor_body_enabled = False
        with self.assertRaises(AccessError):
            self.first_page.with_user(editor).write({"site_editor_body": "<p>Before preparation</p>"})
        for record, values in (
            (self.first_page.view_id, {"name": "New template name"}),
            (self.env.ref("website_site_editor.page_body"), {"name": "Shared frame"}),
            (self.first_page, {"view_id": self.second_page.view_id.id}),
            (self.first_site, {"custom_code_head": "<!-- garden -->"}),
            (self.second_site, {"site_editor_ids": [Command.link(editor.id)]}),
        ):
            with self.assertRaises(AccessError):
                record.with_user(editor).write(values)
        self.assertFalse(self.env["res.config.settings"].with_user(editor).has_access("create"))
        self.first_site.site_editor_ids = [Command.clear()]
        with self.assertRaises(AccessError):
            self.first_page.with_user(editor).write({"site_editor_body": "<p>Fern</p>"})
        admin = self.env.ref("base.user_admin")
        self.second_site.with_user(admin).write({"homepage_url": "/garden-notebook"})
        self.first_page.view_id.with_user(admin).write({"name": "Garden frame"})
        self.assertEqual(self.second_site.homepage_url, self.second_page.url)
        self.assertEqual(self.first_page.view_id.name, "Garden frame")

    def test_builder_image_stays_on_its_site(self) -> None:
        self.authenticate(self.first_editor.login, self.first_editor.login)
        with BytesIO() as data:
            Image.new("RGB", (8, 8), "green").save(data, format="PNG")
            media = self.make_jsonrpc_request(
                "/html_editor/attachment/add_data",
                {
                    "name": "fern.png",
                    "data": base64.b64encode(data.getvalue()).decode(),
                    "is_image": True,
                    "res_model": "website.page",
                    "res_id": self.first_page.id,
                },
            )
        attachment = self.env["ir.attachment"].browse(media["id"])
        self.assertEqual(attachment.website_id, self.first_site)
        with self.assertRaises(AccessError):
            attachment.with_user(self.second_editor).sudo().write({"name": "Other image"})
        with self.assertRaises(AccessError):
            attachment.with_user(self.first_editor).write({"website_id": self.second_site.id})
        self.assertEqual(attachment.name, "fern.png")
        self.assertEqual(attachment.website_id, self.first_site)
        token = attachment.with_user(self.first_editor).generate_access_token()[0]
        image_url = f"/web/image/{attachment.id}?access_token={token}"
        self.first_page.with_user(self.first_editor).write({"site_editor_body": f'<p><img src="{image_url}" alt="Fern"/></p>'})
        self.authenticate(None, None)
        self.assertIn(image_url, self.url_open(self.first_page.url).text)
        self.assertEqual(self.url_open(image_url).headers["Content-Type"].split(";")[0], "image/png")

    def test_scoped_builder_uses_the_target_page_assignment(self) -> None:
        editor = self.first_editor
        template = self.env.ref("website_site_editor.page_body")
        self.authenticate(editor.login, editor.login)
        response = self.url_open(
            "/web/dataset/call_kw/ir.ui.view.save",
            json={
                "jsonrpc": "2.0",
                "method": "call",
                "id": 1,
                "params": {
                    "model": "ir.ui.view",
                    "method": "save",
                    "args": [
                        [template.id],
                        f'<div data-oe-model="website.page" data-oe-id="{self.second_page.id}" data-oe-type="html" data-oe-field="site_editor_body"><p>Garden copy</p></div>',
                    ],
                    "kwargs": {"context": {"website_id": self.first_site.id}},
                },
            },
        )
        self.assertEqual(response.json()["error"]["data"]["name"], "odoo.exceptions.AccessError")
        self.assertEqual(self.second_page.site_editor_body, "<p>Silver leaf</p>")
        with self.assertRaises(AccessError):
            self.env["theme.utils"].with_user(editor).with_context(website_id=self.second_site.id).enable_asset(
                "website.ripple_effect_css"
            )

    def test_grid_layout_survives_an_ordinary_body_save(self) -> None:
        page = self.first_page.with_user(self.first_editor)
        page.write(
            {"site_editor_body": '<section class="o_grid_mode"><div style="grid-area: 1 / 2 / 3 / 4">Golden fern</div></section>'}
        )
        self.assertIn("grid-area", self.first_page.site_editor_body)

    def test_menu_editor_saves_a_navigation_label(self) -> None:
        self.start_tour(self.preview, "site_editor_navigation", login=self.first_editor.login)
        menus = self.env["website.menu"].search([("name", "=", "Garden paths")])
        self.assertEqual(menus.website_id, self.first_site)

    def test_assigned_site_settings_and_page_url_forms(self) -> None:
        self.start_tour(self.preview, "site_editor_settings", login=self.first_editor.login)
        self.assertEqual(self.first_site.homepage_url, self.first_page.url)
        self.start_tour(self.preview, "site_editor_page_url", login=self.first_editor.login)
        self.assertEqual(self.first_page.url, "/fern-notebook")
        self.assertEqual(self.first_site.homepage_url, self.first_page.url)
        self.assertEqual(self.second_page.url, "/garden-notebook")

    def test_other_host_cannot_redirect_a_homepage_rename(self) -> None:
        for site in (self.first_site, self.second_site):
            site.homepage_url = self.second_page.url
        self.second_page.with_user(self.second_editor).with_context(
            website_id=self.first_site.id, lang=self.second_site.default_lang_id.code
        ).write({"url": "/moss-garden"})
        self.assertEqual(self.second_site.homepage_url, "/moss-garden")
        self.assertEqual(self.first_site.homepage_url, self.first_page.url)

    def test_navigation_entry_cannot_become_an_extra_root(self) -> None:
        menus = self.env["website.menu"].with_user(self.first_editor)
        menu = menus.create({"website_id": self.first_site.id, "name": "Trees", "parent_id": False})
        self.assertEqual(menu.parent_id, self.first_site.menu_id)
        with self.assertRaises(AccessError):
            menu.write({"parent_id": False})
        self.assertEqual(menu.parent_id, self.first_site.menu_id)

    def test_native_image_editor_copies_shared_media_onto_the_current_site(self) -> None:
        with BytesIO() as data:
            Image.new("RGB", (8, 8), "green").save(data, format="PNG")
            original = self.env["ir.attachment"].create(
                {
                    "name": "ferns.png",
                    "type": "binary",
                    "raw": data.getvalue(),
                    "public": True,
                    "url": "/website/static/fixture/ferns.png",
                    "res_model": "ir.ui.view",
                }
            )
            data.seek(0)
            data.truncate()
            Image.new("RGB", (4, 4), "green").save(data, format="PNG")
            self.authenticate(self.first_editor.login, self.first_editor.login)
            self.make_jsonrpc_request(
                f"/web_editor/modify_image/{original.id}",
                {
                    "res_model": "website.page",
                    "res_id": self.first_page.id,
                    "data": base64.b64encode(data.getvalue()).decode(),
                    "mimetype": "image/png",
                },
            )
        variant = self.env["ir.attachment"].search([("original_id", "=", original.id)])
        self.assertEqual(variant.website_id, self.first_site)
        self.assertFalse(variant.url)
        self.assertFalse(original.website_id)
        self.assertEqual(original.url, "/website/static/fixture/ferns.png")
