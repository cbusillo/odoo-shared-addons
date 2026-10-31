import json
import os
from typing import Any

from odoo import SUPERUSER_ID, Command, api, fields, models
from odoo.exceptions import AccessDenied, AccessError

from ..policy import COPY_PARAMETER, GROUP, RUNTIME_ENV, canonical_identity, product_login, qualify_runtime
from .base import AUTHENTICATING


class ResUsers(models.Model):
    _inherit = "res.users"

    launchplane_readonly_owner = fields.Json(copy=False, groups=fields.NO_ACCESS)
    launchplane_readonly_runtime = fields.Json(copy=False, groups=fields.NO_ACCESS)

    @api.model
    def _launchplane_readonly_runtime_owner(self, identity: dict) -> dict:
        parameters = self.env["ir.config_parameter"].sudo()
        try:
            return qualify_runtime(
                identity,
                os.environ.get(RUNTIME_ENV, "null"),
                os.environ.get("PLATFORM_INSTANCE", ""),
                self.env.cr.dbname,
                parameters.get_str("database.uuid"),
                parameters.get_str(COPY_PARAMETER),
            )
        except (ValueError, TypeError, KeyError) as error:
            raise AccessError(self.env._("The read-only test target is not qualified.")) from error

    @api.model
    def _launchplane_readonly_group(self) -> "odoo.model.res_groups":
        group = self.env.ref(GROUP)
        internal = self.env.ref("base.group_user")
        forbidden = (
            "base.group_system",
            "base.group_erp_manager",
            "base.group_allow_export",
            "base.group_sanitize_override",
            "stock.group_stock_user",
            "account.group_account_invoice",
            "purchase.group_purchase_user",
            "sales_team.group_sale_salesman",
        )
        if group.implied_ids != internal or any(
            (denied := self.env.ref(xmlid, raise_if_not_found=False)) and denied in group.all_implied_ids for xmlid in forbidden
        ):
            raise AccessError(self.env._("The read-only role has unexpected privileges."))
        return group

    def _launchplane_readonly_check_user(self, owner: dict) -> None:
        self.ensure_one()
        group = self._launchplane_readonly_group()
        if (
            self.id <= 2
            or self.login != product_login(owner["product"])
            or self.launchplane_readonly_owner != owner
            or self.group_ids != group
            or self.all_group_ids != group.all_implied_ids
            or self.share
            or self.env["res.users.apikeys"].sudo().search_count([("user_id", "=", self.id)])
            or any(self[name] for name in ("oauth_provider_id", "oauth_uid", "oauth_access_token") if name in self._fields)
        ):
            raise AccessError(self.env._("The test account ownership or privileges changed."))

    @api.model
    def _launchplane_readonly_identity(self, identity: dict, login: str, *, create: bool, fixture: bool) -> "odoo.model.res_users":
        if self.env.uid != SUPERUSER_ID or not self.env.su:
            raise AccessError(self.env._("Only the native test-account consumer can qualify an identity."))
        owner = self._launchplane_readonly_runtime_owner(identity)
        if login != product_login(owner["product"]) or (fixture and owner["environment_kind"] != "preview"):
            raise AccessError(self.env._("The test account does not belong to this target."))
        if create and owner["environment_kind"] == "preview" and not fixture:
            raise AccessError(self.env._("Preview test accounts require the product fixture."))
        group = self._launchplane_readonly_group()
        users = self.with_context(active_test=False, no_reset_password=True, tracking_disable=True, mail_create_nosubscribe=True)
        user = users.search(fields.Domain("login", "=", login))
        if not user and create:
            values = {
                "name": "TEST Read-only QA",
                "login": login,
                "active": False,
                "tz": "UTC",
                "group_ids": [Command.set(group.ids)],
                "launchplane_readonly_owner": owner,
                "email": False,
            }
            values.update(
                {name: False for name in ("oauth_provider_id", "oauth_uid", "oauth_access_token") if name in users._fields}
            )
            if "odoobot_state" in users._fields:
                values["odoobot_state"] = "disabled"
            user = users.create(values)
            if "res.users.settings" in self.env.registry:
                self.env["res.users.settings"]._find_or_create_for_user(user)
        if not user and fixture:
            return user
        if len(user) != 1:
            raise AccessError(self.env._("The owned test account is missing."))
        user._launchplane_readonly_check_user(owner)
        return user

    @api.model
    def _launchplane_readonly_test_identity(self, identity: dict, login: str, create: bool = False) -> "odoo.model.res_users":
        return self._launchplane_readonly_identity(identity, login, create=create, fixture=False)

    @api.model
    def _launchplane_readonly_fixture_identity(self, identity: dict, create: bool = False) -> "odoo.model.res_users":
        login = product_login(identity.get("product", ""))
        return self._launchplane_readonly_identity(identity, login, create=create, fixture=True)

    def write(self, values: dict[str, Any]) -> bool:
        owned = self.sudo().filtered("launchplane_readonly_owner")
        activating = owned and self.env.uid == SUPERUSER_ID and values.get("active") is True
        if owned and self.env.uid == SUPERUSER_ID and ("password" in values or values.get("active")):
            identity = json.loads(os.environ.get(RUNTIME_ENV, "null"))
            owner = self._launchplane_readonly_runtime_owner(identity)
            for user in owned:
                user._launchplane_readonly_check_user(owner)
            values = dict(values, launchplane_readonly_runtime=canonical_identity(identity))
        if activating and "odoobot_state" in self._fields:
            values = dict(values, odoobot_state="disabled")
        result = super().write(values)
        if activating:
            for user in owned:
                user._launchplane_readonly_prepare_webclient()
        return result

    def _launchplane_readonly_prepare_webclient(self) -> None:
        self.ensure_one()
        qweb = self.env["ir.qweb"].with_context(lang=self.lang)
        qweb._pregenerate_assets_bundles()
        if self.env["res.lang"]._lang_get(self.lang).direction == "rtl":
            for bundle in qweb._get_bundles_to_pregenarate()[1]:
                qweb._get_asset_bundle(bundle, css=True, js=False, rtl=True).css()

    @api.model
    @api.readonly
    def action_get(self) -> dict:
        return super().action_get()

    def _check_credentials(self, credential: dict, env: dict) -> dict:
        if self._launchplane_readonly_actor():
            if env.get("interactive") is not True or credential.get("type") != "password":
                raise AccessDenied()
            try:
                self._launchplane_readonly_check_session()
            except (AccessError, ValueError, TypeError) as error:
                raise AccessDenied() from error
        return super()._check_credentials(credential, env)

    def _launchplane_readonly_check_session(self) -> None:
        identity = json.loads(os.environ.get(RUNTIME_ENV, "null"))
        user = self.sudo()
        user._launchplane_readonly_check_user(user._launchplane_readonly_runtime_owner(identity))
        if (
            not user.active
            or user.launchplane_readonly_runtime != canonical_identity(identity)
            or ("odoobot_state" in user._fields and user.odoobot_state != "disabled")
        ):
            raise AccessError(self.env._("This test identity is not active on the current runtime."))

    def _login(self, credential: dict, user_agent_env: dict) -> dict:
        token = AUTHENTICATING.set(True)
        try:
            return super()._login(credential, user_agent_env)
        finally:
            AUTHENTICATING.reset(token)
