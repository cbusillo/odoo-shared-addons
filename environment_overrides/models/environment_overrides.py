import logging
import os
from collections.abc import Iterable

from odoo import models
from odoo.exceptions import ValidationError

from odoo.addons.launchplane_settings.models.launchplane_settings import (  # noqa: F401
    ODOO_INSTANCE_OVERRIDES_PAYLOAD_ENV_KEY,
    _normalize_config_param_value,
    _parse_boolean,
)

_logger = logging.getLogger(__name__)

CONFIG_PARAM_PREFIX = "ENV_OVERRIDE_CONFIG_PARAM__"
SHOPIFY_PREFIX = "ENV_OVERRIDE_SHOPIFY__"
AUTHENTIK_CONFIG_MODEL = "authentik.sso.config"
AUTHENTIK_GROUP_MAPPING_MODEL = "authentik.sso.group.mapping"


def _normalized_env_suffixes(*, prefix: str, excluded_suffixes: Iterable[str] = ()) -> dict[str, str]:
    overrides: dict[str, str] = {}
    normalized_exclusions = {item.strip().lower() for item in excluded_suffixes if item.strip()}
    prefix_length = len(prefix)
    for raw_key, raw_value in os.environ.items():
        if not raw_key.startswith(prefix):
            continue
        if len(raw_key) <= prefix_length:
            continue
        suffix = raw_key[prefix_length:].strip().lower()
        if not suffix or suffix in normalized_exclusions:
            continue
        overrides[suffix] = raw_value
    return overrides


class EnvironmentOverrides(models.AbstractModel):
    _name = "environment.overrides"
    _description = "Legacy Environment Overrides Compatibility Adapter"

    def apply_from_env(self) -> None:
        typed_payload_present = bool(os.environ.get(ODOO_INSTANCE_OVERRIDES_PAYLOAD_ENV_KEY, "").strip())
        if typed_payload_present:
            if "launchplane.settings" not in self.env.registry:
                raise ValidationError(
                    "Launchplane supplied ODOO_INSTANCE_OVERRIDES_PAYLOAD_B64, "
                    "but launchplane.settings is not installed."
                )
            _logger.info("Delegating typed environment.overrides payload to launchplane.settings.")
            self.env["launchplane.settings"].sudo().apply_from_env()
            return

        legacy_env_present = any(key.startswith("ENV_OVERRIDE_") for key in os.environ)
        if not legacy_env_present:
            return

        _logger.warning(
            "Applying legacy ENV_OVERRIDE_* settings through environment.overrides. "
            "Move this caller to Launchplane-managed Odoo instance settings."
        )
        self._apply_legacy_config_param_overrides()
        self._apply_legacy_authentik_overrides()
        self._apply_legacy_shopify_overrides()

    def _apply_legacy_config_param_overrides(self) -> None:
        overrides: dict[str, str] = {}
        for suffix, raw_value in _normalized_env_suffixes(prefix=CONFIG_PARAM_PREFIX).items():
            param_key = suffix.replace("__", ".")
            overrides[param_key] = _normalize_config_param_value(raw_value)

        if not overrides:
            return

        parameter_model = self.env["ir.config_parameter"].sudo()
        _logger.info("Applying %d legacy config parameter overrides.", len(overrides))
        for key, value in overrides.items():
            parameter_model.set_param(key, value)

    def _apply_legacy_authentik_overrides(self) -> None:
        authentik_config_model = self.env.get(AUTHENTIK_CONFIG_MODEL)
        if authentik_config_model is None:
            return

        apply_from_env = getattr(authentik_config_model.sudo(), "apply_from_env", None)
        if callable(apply_from_env):
            apply_from_env()

        group_mapping_model = self.env.get(AUTHENTIK_GROUP_MAPPING_MODEL)
        if group_mapping_model is None:
            return

        ensure_default_mappings = getattr(group_mapping_model.sudo(), "ensure_default_mappings", None)
        if callable(ensure_default_mappings):
            ensure_default_mappings()

    def _apply_legacy_shopify_overrides(self) -> None:
        overrides = _normalized_env_suffixes(prefix=SHOPIFY_PREFIX)
        if not overrides:
            return

        if "launchplane.settings" not in self.env.registry:
            if os.environ.get(ODOO_INSTANCE_OVERRIDES_PAYLOAD_ENV_KEY, "").strip():
                raise ValidationError(
                    "Launchplane supplied ODOO_INSTANCE_OVERRIDES_PAYLOAD_B64, "
                    "but launchplane.settings is not installed."
                )
            _logger.warning("launchplane.settings is not installed; skipping legacy Shopify overrides.")
            return

        self.env["launchplane.settings"].sudo()._apply_shopify_overrides_from_values(overrides)
