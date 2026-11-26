from odoo.api import Environment


def pre_init_hook(env: Environment) -> None:
    view = env.ref("authentik_sso.staff_login", raise_if_not_found=False)
    if view:
        env["ir.model.data"]._update_xmlids([{"xml_id": "authentik_sso_login.staff_login", "record": view}])
