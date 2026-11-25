from typing import Literal

from odoo import fields, models
from odoo.api import Environment
from odoo.exceptions import AccessError

PAGE_FIELD_ACCESS = object()


def is_site_editor(env: Environment) -> bool:
    return env.user.has_group("website_site_editor.group_editor") and not env.user.has_group("base.group_system")


def denied(env: Environment) -> AccessError:
    return AccessError(env._("This change requires a website administrator or an assignment to this website."))


class SiteEditorFields(models.AbstractModel):
    _name = "website.site.editor.fields"
    _description = "Fields editable by an assigned website editor"

    _site_editor_fields: frozenset[str] = frozenset()

    def _has_field_access(self, field: fields.Field, operation: Literal["read", "write"]) -> bool:
        if operation == "write" and is_site_editor(self.env) and field.name not in self._site_editor_fields:
            return False
        return super()._has_field_access(field, operation)
