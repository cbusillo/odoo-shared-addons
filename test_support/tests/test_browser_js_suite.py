from types import SimpleNamespace
from unittest import SkipTest
from unittest.mock import Mock, patch

from .common_imports import common
from .fixtures.base_cases import run_browser_js_suite


@common.tagged(*common.UNIT_TAGS)
class TestBrowserJsSuite(common.TransactionCase):
    def _run(self, side_effect=None, **kwargs):
        browser_js = Mock(side_effect=side_effect)
        test_case = SimpleNamespace(
            browser_js=browser_js, _get_test_login=lambda: "suite-user"
        )
        with patch(f"{run_browser_js_suite.__module__}.wait_for_browser_endpoint"):
            run_browser_js_suite(
                test_case,
                "/suite",
                success_signal="suite passed",
                error_checker=None,
                **kwargs,
            )
        return browser_js

    def test_success_waits_for_requested_signal(self) -> None:
        browser_js = self._run(timeout=23)
        browser_js.assert_called_once_with(
            "/suite",
            code="",
            login="suite-user",
            timeout=23,
            success_signal="suite passed",
            error_checker=None,
        )

    def test_browser_failures_propagate(self) -> None:
        for error in (
            AssertionError("[HOOT] failed"),
            RuntimeError("browser failed"),
            TimeoutError("timed out"),
        ):
            with self.subTest(error=error):
                with self.assertRaises(type(error)) as caught:
                    self._run(error)
                self.assertIs(caught.exception, error)

    def test_missing_browser_remains_a_skip(self) -> None:
        error = SkipTest("no browser")
        with self.assertRaises(SkipTest) as caught:
            self._run(error)
        self.assertIs(caught.exception, error)

    def test_timeout_retry_can_succeed(self) -> None:
        browser_js = self._run([TimeoutError(), None], timeout=17, retry_timeout=29)
        self.assertEqual(
            [call.kwargs["timeout"] for call in browser_js.call_args_list], [17, 29]
        )

    def test_retry_failure_propagates(self) -> None:
        for error in (
            AssertionError("[HOOT] failed"),
            RuntimeError("browser failed"),
            TimeoutError("timed out"),
        ):
            with self.subTest(error=error):
                with self.assertRaises(type(error)) as caught:
                    self._run([TimeoutError(), error], retry_timeout=29)
                self.assertIs(caught.exception, error)
