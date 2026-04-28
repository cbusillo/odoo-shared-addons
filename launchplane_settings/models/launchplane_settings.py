import base64
import binascii
import json
import logging
import os
from collections.abc import Iterable, Mapping

from odoo import models
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)

ODOO_INSTANCE_OVERRIDES_PAYLOAD_ENV_KEY = "ODOO_INSTANCE_OVERRIDES_PAYLOAD_B64"
SHOPIFY_ACTION_SETTING = "action"
SHOPIFY_ACTION_APPLY = "apply"
SHOPIFY_ACTION_CLEAR = "clear"
AUTHENTIK_CONFIG_MODEL = "authentik.sso.config"
AUTHENTIK_GROUP_MAPPING_MODEL = "authentik.sso.group.mapping"

FALSE_VALUES = {"", "0", "false", "no", "off"}
TRUE_VALUES = {"1", "true", "yes", "on"}
DEFAULT_PRODUCTION_INDICATORS = ("production", "live", "prod-")


def _normalize_config_param_value(raw_value: str) -> str:
    value = raw_value.strip()
    lowered = value.lower()
    if lowered in FALSE_VALUES:
        return "False"
    if lowered in TRUE_VALUES:
        return "True"
    return value


def _parse_boolean(raw_value: str | None, *, default: bool) -> bool:
    if raw_value is None:
        return default
    value = raw_value.strip().lower()
    if value in FALSE_VALUES:
        return False
    if value in TRUE_VALUES:
        return True
    return default


def _normalize_scalar_override_value(raw_value: object) -> str:
    if isinstance(raw_value, bool):
        return "True" if raw_value else "False"
    return _normalize_config_param_value(str(raw_value))


def _load_override_payload() -> Mapping[str, object] | None:
    encoded_payload = os.environ.get(ODOO_INSTANCE_OVERRIDES_PAYLOAD_ENV_KEY, "").strip()
    if not encoded_payload:
        return None
    try:
        decoded_payload = base64.b64decode(encoded_payload, validate=True)
        payload = json.loads(decoded_payload.decode("utf-8"))
    except (ValueError, UnicodeDecodeError, binascii.Error, json.JSONDecodeError) as error:
        raise ValidationError("Invalid Odoo instance override payload.") from error
    if not isinstance(payload, dict):
        raise ValidationError("Odoo instance override payload must decode to an object.")
    return payload


def _payload_items(payload: Mapping[str, object] | None, key: str) -> tuple[Mapping[str, object], ...]:
    if payload is None:
        return ()
    raw_items = payload.get(key)
    if raw_items is None:
        return ()
    if not isinstance(raw_items, list):
        raise ValidationError(f"Odoo instance override payload field '{key}' must be a list.")
    items: list[Mapping[str, object]] = []
    for raw_item in raw_items:
        if not isinstance(raw_item, dict):
            raise ValidationError(f"Odoo instance override payload field '{key}' must contain objects.")
        items.append(raw_item)
    return tuple(items)


def _payload_value_for_setting(*, raw_value: object, override_name: str) -> str:
    if not isinstance(raw_value, dict):
        raise ValidationError(f"Odoo override '{override_name}' has an invalid value payload.")
    source = str(raw_value.get("source") or "").strip()
    if source == "literal":
        if "value" not in raw_value:
            raise ValidationError(f"Odoo override '{override_name}' is missing a literal value.")
        return _normalize_scalar_override_value(raw_value.get("value"))
    if source == "secret_binding":
        environment_variable = str(raw_value.get("environment_variable") or "").strip()
        if not environment_variable:
            raise ValidationError(
                f"Secret-backed Odoo override '{override_name}' is missing its runtime environment variable."
            )
        if environment_variable not in os.environ:
            raise ValidationError(
                f"Secret-backed Odoo override '{override_name}' is missing environment variable {environment_variable}."
            )
        return os.environ.get(environment_variable, "")
    raise ValidationError(f"Odoo override '{override_name}' has unsupported source '{source}'.")


class LaunchplaneSettings(models.AbstractModel):
    _name = "launchplane.settings"
    _description = "Launchplane Settings Apply Adapter"

    def apply_from_env(self) -> None:
        payload = _load_override_payload()
        if payload is None:
            return
        self._apply_config_param_overrides(payload=payload)
        self._apply_authentik_overrides(payload=payload)
        self._apply_shopify_overrides(payload=payload)

    def _payload_config_param_overrides(self, payload: Mapping[str, object] | None) -> dict[str, str]:
        overrides: dict[str, str] = {}
        for item in _payload_items(payload, "config_parameters"):
            key = str(item.get("key") or "").strip().lower()
            if not key:
                raise ValidationError("Odoo config parameter override payload entries require key.")
            overrides[key] = _payload_value_for_setting(raw_value=item.get("value"), override_name=key)
        return overrides

    def _apply_config_param_overrides(self, *, payload: Mapping[str, object] | None = None) -> None:
        payload_overrides = self._payload_config_param_overrides(payload)
        if not payload_overrides:
            return

        parameter_model = self.env["ir.config_parameter"].sudo()
        _logger.info(
            "Applying %d Launchplane config parameter overrides.",
            len(payload_overrides),
        )
        for key, value in payload_overrides.items():
            parameter_model.set_param(key, value)

    def _payload_addon_overrides(
        self,
        payload: Mapping[str, object] | None,
        *,
        addon_names: Iterable[str],
    ) -> dict[str, str]:
        normalized_addons = {addon.strip().lower() for addon in addon_names if addon.strip()}
        overrides: dict[str, str] = {}
        for item in _payload_items(payload, "addon_settings"):
            addon_name = str(item.get("addon") or "").strip().lower()
            if addon_name not in normalized_addons:
                continue
            setting_name = str(item.get("setting") or "").strip().lower()
            if not setting_name:
                raise ValidationError("Odoo addon override payload entries require setting.")
            override_name = f"{addon_name}.{setting_name}"
            overrides[setting_name] = _payload_value_for_setting(
                raw_value=item.get("value"),
                override_name=override_name,
            )
        return overrides

    def _apply_authentik_overrides(self, *, payload: Mapping[str, object] | None = None) -> None:
        payload_overrides = self._payload_addon_overrides(payload, addon_names=("authentik", "authentik_sso"))
        if not payload_overrides:
            return

        authentik_config_model = self.env.get(AUTHENTIK_CONFIG_MODEL)
        if authentik_config_model is None:
            return

        apply_from_values = getattr(authentik_config_model.sudo(), "apply_from_values", None)
        if callable(apply_from_values):
            apply_from_values(payload_overrides)

        group_mapping_model = self.env.get(AUTHENTIK_GROUP_MAPPING_MODEL)
        if group_mapping_model is None:
            return

        ensure_default_mappings = getattr(group_mapping_model.sudo(), "ensure_default_mappings", None)
        if callable(ensure_default_mappings):
            ensure_default_mappings()

    def _apply_shopify_overrides_from_values(self, overrides: Mapping[str, str]) -> None:
        shop_url_key = overrides.get("shop_url_key", "").strip()
        api_token = overrides.get("api_token", "").strip()
        webhook_key = overrides.get("webhook_key", "").strip()
        api_version = overrides.get("api_version", "").strip()
        test_store_raw = overrides.get("test_store")
        test_store = _parse_boolean(test_store_raw, default=False)
        allow_production = _parse_boolean(overrides.get("allow_production"), default=False)

        indicators_raw = overrides.get("production_indicators")
        if indicators_raw is None:
            production_indicators = list(DEFAULT_PRODUCTION_INDICATORS)
        else:
            cleaned = [item.strip().lower() for item in indicators_raw.split(",") if item.strip()]
            production_indicators = cleaned or list(DEFAULT_PRODUCTION_INDICATORS)

        required_values = [shop_url_key, api_token, webhook_key, api_version]
        if not all(required_values):
            self._clear_shopify_config()
            if any(required_values):
                _logger.warning("Shopify overrides incomplete; cleared Shopify configuration.")
            else:
                _logger.info("Shopify overrides missing; cleared Shopify configuration.")
            return

        shop_url_lower = shop_url_key.lower()
        matched_indicator = ""
        for indicator in production_indicators:
            if indicator and indicator in shop_url_lower:
                matched_indicator = indicator
                break
        if matched_indicator and not allow_production:
            raise ValidationError(
                "Shopify shop_url_key "
                f"'{shop_url_key}' appears to be production (indicator: '{matched_indicator}'). "
                "Set the Launchplane Shopify allow_production setting only when this is intentional."
            )
        if matched_indicator and allow_production:
            _logger.warning(
                "Allowing production-like Shopify key '%s' because Launchplane supplied allow_production=true.",
                shop_url_key,
            )

        parameter_model = self.env["ir.config_parameter"].sudo()
        parameter_model.set_param("shopify.shop_url_key", shop_url_key)
        parameter_model.set_param("shopify.api_token", api_token)
        parameter_model.set_param("shopify.webhook_key", webhook_key)
        parameter_model.set_param("shopify.api_version", api_version)
        parameter_model.set_param("shopify.test_store", "True" if test_store else "False")
        self._remove_shopify_legacy_keys()
        self._update_shopify_external_urls(shop_url_key)

    def _apply_shopify_overrides(self, *, payload: Mapping[str, object] | None = None) -> None:
        payload_overrides = self._payload_addon_overrides(payload, addon_names=("shopify",))
        payload_action = payload_overrides.get(SHOPIFY_ACTION_SETTING, "").strip().lower()
        if payload_action:
            self._apply_shopify_payload_action(payload_overrides)
            return
        if not payload_overrides:
            return
        self._apply_shopify_overrides_from_values(payload_overrides)

    def _apply_shopify_payload_action(self, overrides: Mapping[str, str]) -> None:
        payload_action = overrides.get(SHOPIFY_ACTION_SETTING, "").strip().lower()
        if payload_action == SHOPIFY_ACTION_CLEAR:
            self._clear_shopify_config()
            _logger.info("Applied Launchplane Shopify clear action.")
            return
        if payload_action != SHOPIFY_ACTION_APPLY:
            raise ValidationError(f"Unsupported Shopify override action '{payload_action}'.")

        shop_url_key = overrides.get("shop_url_key", "").strip()
        api_token = overrides.get("api_token", "").strip()
        webhook_key = overrides.get("webhook_key", "").strip()
        api_version = overrides.get("api_version", "").strip()
        required_values = [shop_url_key, api_token, webhook_key, api_version]
        if not all(required_values):
            raise ValidationError("Launchplane Shopify apply action is missing required values.")

        test_store_raw = overrides.get("test_store")
        test_store = _parse_boolean(test_store_raw, default=False)

        parameter_model = self.env["ir.config_parameter"].sudo()
        parameter_model.set_param("shopify.shop_url_key", shop_url_key)
        parameter_model.set_param("shopify.api_token", api_token)
        parameter_model.set_param("shopify.webhook_key", webhook_key)
        parameter_model.set_param("shopify.api_version", api_version)
        parameter_model.set_param("shopify.test_store", "True" if test_store else "False")
        self._remove_shopify_legacy_keys()
        self._update_shopify_external_urls(shop_url_key)

    def _clear_shopify_config(self) -> None:
        parameter_model = self.env["ir.config_parameter"].sudo()
        keys = [
            "shopify.shop_url_key",
            "shopify.api_token",
            "shopify.webhook_key",
            "shopify.api_version",
            "shopify.test_store",
            "shopify.shop_url",
            "shopify.store_url",
        ]
        records = parameter_model.search([("key", "in", keys)])
        if records:
            records.unlink()

    def _remove_shopify_legacy_keys(self) -> None:
        parameter_model = self.env["ir.config_parameter"].sudo()
        legacy_keys = ["shopify.shop_url", "shopify.store_url"]
        records = parameter_model.search([("key", "in", legacy_keys)])
        if records:
            records.unlink()

    @staticmethod
    def _normalize_shopify_storefront_base(shop_url_key: str) -> str:
        from urllib.parse import urlsplit

        raw_value = (shop_url_key or "").strip().strip("/")
        if not raw_value:
            return ""

        lower_value = raw_value.lower()
        http_prefix = "http" + "://"
        https_prefix = "https" + "://"
        if lower_value.startswith(http_prefix) or lower_value.startswith(https_prefix):
            parts = urlsplit(raw_value)
            netloc = parts.netloc
            if not netloc:
                return ""
            return f"{parts.scheme}://{netloc}"

        raw_value = raw_value.split("/", 1)[0]
        raw_value = raw_value.split("?", 1)[0].split("#", 1)[0]
        if raw_value.endswith(".myshopify.com"):
            return f"https://{raw_value}"
        if "." in raw_value:
            return f"https://{raw_value}"
        return f"https://{raw_value}.myshopify.com"

    @staticmethod
    def _derive_shopify_admin_store_key(shop_url_key: str) -> str:
        from urllib.parse import urlsplit

        raw_value = (shop_url_key or "").strip().strip("/")
        if not raw_value:
            return ""

        lower_value = raw_value.lower()
        http_prefix = "http" + "://"
        https_prefix = "https" + "://"
        if lower_value.startswith(http_prefix) or lower_value.startswith(https_prefix):
            parts = urlsplit(raw_value)
            host = parts.netloc
        else:
            host = raw_value.split("/", 1)[0]
        host = host.split("?", 1)[0].split("#", 1)[0]

        if host.endswith(".myshopify.com"):
            return host.split(".", 1)[0]
        if "." in host:
            return ""
        return host

    def _update_shopify_external_urls(self, shop_url_key: str) -> None:
        external_system_model = self.env.get("external.system")
        external_system_url_model = self.env.get("external.system.url")
        if external_system_model is None or external_system_url_model is None:
            return

        system = external_system_model.sudo().search([("code", "=", "shopify")], limit=1)
        if not system:
            return

        storefront_base = self._normalize_shopify_storefront_base(shop_url_key)
        admin_store_key = self._derive_shopify_admin_store_key(shop_url_key)
        admin_base = f"https://admin.shopify.com/store/{admin_store_key}" if admin_store_key else ""

        system_url = system["url"] if "url" in system._fields else ""
        if storefront_base and system_url != storefront_base:
            system.write({"url": storefront_base})

        url_templates = external_system_url_model.sudo().search(
            [
                ("system_id", "=", system.id),
                ("code", "in", ["customer_admin", "product_admin", "product_store"]),
            ]
        )
        for url_template in url_templates:
            url_code = url_template["code"] if "code" in url_template._fields else ""
            if url_code in {"customer_admin", "product_admin"}:
                base_url = admin_base
            else:
                base_url = storefront_base
            if not base_url:
                continue
            template_base_url = url_template["base_url"] if "base_url" in url_template._fields else ""
            if template_base_url != base_url:
                url_template.write({"base_url": base_url})
