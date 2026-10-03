from datetime import datetime
from typing import Any, Union
from unittest.mock import MagicMock, Mock

OdooValue = Union[str, int, float, bool, None, list, tuple, datetime, bytes]


MockType = Union[MagicMock, Mock]

AssertionDict = dict[str, Any]

DEFAULT_TEST_CONTEXT = {
    "tracking_disable": True,
    "no_reset_password": True,
    "mail_create_nosubscribe": True,
    "mail_create_nolog": True,
    "mail_notrack": True,
}

STANDARD_TAGS = ["post_install", "-at_install"]
UNIT_TAGS = STANDARD_TAGS + ["unit_test"]
INTEGRATION_TAGS = STANDARD_TAGS + ["integration_test"]
TOUR_TAGS = STANDARD_TAGS + ["tour_test"]
JS_TAGS = STANDARD_TAGS + ["js_test"]
PERFORMANCE_TAGS = STANDARD_TAGS + ["performance_test"]

TEST_SKU_PREFIX = "TEST"

__all__ = [
    "OdooValue",
    "MockType",
    "AssertionDict",
    "DEFAULT_TEST_CONTEXT",
    "STANDARD_TAGS",
    "UNIT_TAGS",
    "INTEGRATION_TAGS",
    "TOUR_TAGS",
    "JS_TAGS",
    "PERFORMANCE_TAGS",
    "TEST_SKU_PREFIX",
]
