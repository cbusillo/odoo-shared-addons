import logging
import os
from collections.abc import Mapping

from odoo import models
from odoo.exceptions import AccessError, UserError, ValidationError

_logger = logging.getLogger(__name__)

AUTHENTIK_PREFIX = "ENV_OVERRIDE_AUTHENTIK__"
AUTHENTIK_ADMIN_GROUP_PARAM = "authentik_sso.admin_group"
AUTHENTIK_GROUP_CLAIM_PARAM = "authentik_sso.group_claim"
AUTHENTIK_LOGIN_CLAIMS_PARAM = "authentik_sso.login_claims"
AUTHENTIK_NAME_CLAIMS_PARAM = "authentik_sso.name_claims"
AUTHENTIK_PROVIDER_NAME_PARAM = "authentik_sso.provider_name"
AUTHENTIK_USER_ID_CLAIMS_PARAM = "authentik_sso.user_id_claims"


DEFAULT_ADMIN_GROUP = "authentik Admins"
DEFAULT_GROUP_CLAIM = "groups"
DEFAULT_LOGIN_CLAIMS = "email,preferred_username,username,login"
DEFAULT_NAME_CLAIMS = "name,full_name,display_name,preferred_username,username,email"
DEFAULT_PROVIDER_NAME = "Authentik"
DEFAULT_SCOPE = "openid profile email"
DEFAULT_LOGIN_LABEL = "Sign in with Authentik"
DEFAULT_CSS_CLASS = "fa fa-fw fa-sign-in text-primary"
DEFAULT_USER_ID_CLAIMS = "user_id,sub,id,uid"


def _split_list(raw_value: str | None) -> list[str]:
    if raw_value is None:
        return []
    return [item.strip() for item in raw_value.split(",") if item.strip()]


def _normalize_base_url(raw_value: str | None) -> str | None:
    if raw_value is None:
        return None
    cleaned = raw_value.strip().rstrip("/")
    return cleaned or None


def _clean_setting_value(raw_value: str | None, *, default: str) -> str:
    if raw_value is None:
        return default
    cleaned = raw_value.strip()
    return cleaned or default


class AuthentikSsoConfig(models.AbstractModel):
    _name = "authentik.sso.config"
    _description = "Authentik SSO configuration"

    def apply_from_env(self) -> None:
        self.apply_from_values(self._values_from_env())

    def apply_from_values(self, overrides: Mapping[str, str | None]) -> None:
        self._apply_runtime_settings(overrides)
        self._disable_oauth_providers(overrides)
        self._apply_authentik_provider(overrides)

    @staticmethod
    def _values_from_env() -> dict[str, str]:
        overrides: dict[str, str] = {}
        prefix_length = len(AUTHENTIK_PREFIX)
        for raw_key, raw_value in os.environ.items():
            if not raw_key.startswith(AUTHENTIK_PREFIX):
                continue
            suffix = raw_key[prefix_length:].strip().lower()
            if not suffix:
                continue
            overrides[suffix] = raw_value
        return overrides

    def _apply_runtime_settings(self, overrides: Mapping[str, str | None]) -> None:
        parameter_model = self.env["ir.config_parameter"].sudo()
        parameter_model.set_param(
            AUTHENTIK_ADMIN_GROUP_PARAM,
            _clean_setting_value(
                overrides.get("admin_group"), default=DEFAULT_ADMIN_GROUP
            ),
        )
        parameter_model.set_param(
            AUTHENTIK_GROUP_CLAIM_PARAM,
            _clean_setting_value(
                overrides.get("group_claim"), default=DEFAULT_GROUP_CLAIM
            ),
        )
        parameter_model.set_param(
            AUTHENTIK_LOGIN_CLAIMS_PARAM,
            _clean_setting_value(
                overrides.get("login_claims"), default=DEFAULT_LOGIN_CLAIMS
            ),
        )
        parameter_model.set_param(
            AUTHENTIK_NAME_CLAIMS_PARAM,
            _clean_setting_value(
                overrides.get("name_claims"), default=DEFAULT_NAME_CLAIMS
            ),
        )
        parameter_model.set_param(
            AUTHENTIK_PROVIDER_NAME_PARAM,
            _clean_setting_value(
                overrides.get("provider_name"), default=DEFAULT_PROVIDER_NAME
            ),
        )
        parameter_model.set_param(
            AUTHENTIK_USER_ID_CLAIMS_PARAM,
            _clean_setting_value(
                overrides.get("user_id_claims"), default=DEFAULT_USER_ID_CLAIMS
            ),
        )

    def _disable_oauth_providers(self, overrides: Mapping[str, str | None]) -> None:
        disabled_raw = overrides.get("disable_providers")
        disabled_names = _split_list(disabled_raw)
        if not disabled_names:
            return
        provider_model = self.env["auth.oauth.provider"].sudo()
        providers = provider_model.search([])
        if not providers:
            return
        lowered_terms = {term.casefold() for term in disabled_names}
        to_disable = provider_model.browse()
        for provider in providers:
            provider_name = (provider.name or "").casefold()
            if provider_name in lowered_terms:
                to_disable |= provider
                continue
            auth_endpoint = (provider.auth_endpoint or "").casefold()
            if any(term in auth_endpoint for term in lowered_terms):
                to_disable |= provider

        if not to_disable:
            return
        to_disable.write({"enabled": False})
        _logger.info(
            "Disabled OAuth providers: %s", ", ".join(sorted(to_disable.mapped("name")))
        )

    def _apply_authentik_provider(self, overrides: Mapping[str, str | None]) -> None:
        provider_name = (
            overrides.get("provider_name") or DEFAULT_PROVIDER_NAME
        ).strip()
        if not provider_name:
            provider_name = DEFAULT_PROVIDER_NAME
        client_id = (overrides.get("client_id") or "").strip()
        base_url = _normalize_base_url(overrides.get("base_url"))
        authorization_endpoint = (overrides.get("authorization_endpoint") or "").strip()
        userinfo_endpoint = (overrides.get("userinfo_endpoint") or "").strip()
        scope = (overrides.get("scope") or DEFAULT_SCOPE).strip()
        login_label = (overrides.get("login_label") or DEFAULT_LOGIN_LABEL).strip()
        css_class = (overrides.get("css_class") or DEFAULT_CSS_CLASS).strip()
        data_endpoint = (overrides.get("data_endpoint") or "").strip()

        if base_url:
            if not authorization_endpoint:
                authorization_endpoint = f"{base_url}/application/o/authorize/"
            if not userinfo_endpoint:
                userinfo_endpoint = f"{base_url}/application/o/userinfo/"
            if not data_endpoint:
                data_endpoint = f"{base_url}/application/o/token/"

        provider_model = self.env["auth.oauth.provider"].sudo()
        provider = provider_model.search([("name", "=", provider_name)], limit=1)

        required_missing = (
            not client_id
            or not base_url
            or not authorization_endpoint
            or not userinfo_endpoint
        )
        if required_missing:
            if provider:
                provider.write(
                    {
                        "enabled": False,
                        "client_id": False,
                        "auth_endpoint": False,
                        "validation_endpoint": False,
                        "data_endpoint": False,
                        "scope": False,
                        "css_class": False,
                        "body": False,
                    }
                )
                _logger.info(
                    "Authentik overrides missing; disabled provider '%s'.",
                    provider_name,
                )
            else:
                _logger.info(
                    "Authentik overrides missing; provider '%s' not found.",
                    provider_name,
                )
            return

        values: "odoo.values.auth_oauth_provider" = {
            "name": provider_name,
            "client_id": client_id,
            "auth_endpoint": authorization_endpoint,
            "validation_endpoint": userinfo_endpoint,
            "data_endpoint": data_endpoint or False,
            "scope": scope,
            "enabled": True,
            "css_class": css_class,
            "body": login_label,
        }
        try:
            if provider:
                provider.write(values)
                _logger.info("Updated Authentik provider '%s'.", provider_name)
            else:
                provider_model.create({**values, "sequence": 10})
                _logger.info("Created Authentik provider '%s'.", provider_name)
        except (
            AccessError,
            UserError,
            ValidationError,
            ValueError,
        ):  # pragma: no cover - defensive logging
            _logger.exception(
                "Failed to apply Authentik overrides; disabling provider if present."
            )
            if provider:
                try:
                    provider.write({"enabled": False})
                except (
                    AccessError,
                    UserError,
                    ValidationError,
                    ValueError,
                ):  # pragma: no cover - best-effort disable
                    _logger.exception(
                        "Failed to disable Authentik provider after error."
                    )
