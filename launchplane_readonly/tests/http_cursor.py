from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any
from unittest.mock import patch

from odoo.http import request
from odoo.tests import HttpCase


@contextmanager
def initial_writable_cursor(case: HttpCase, path_prefix: str = "/web/dataset/call_kw") -> Iterator[None]:
    native_cursor = case.registry.cursor
    native_mode = case._registry_readonly_enabled
    case.set_registry_readonly_mode(True)
    first = True

    def cursor(readonly: bool = False) -> Any:
        nonlocal first
        if first and request and request.httprequest.path.startswith(path_prefix):
            first = False
            return native_cursor()
        return native_cursor(readonly=readonly)

    try:
        with patch.object(case.registry, "cursor", cursor):
            yield
    finally:
        case.set_registry_readonly_mode(native_mode)
