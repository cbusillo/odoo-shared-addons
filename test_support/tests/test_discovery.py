import importlib
import sys
import tempfile
import uuid
from pathlib import Path

from .common_imports import common
from .discovery import expose_module_alias, expose_subdirectory_tests


@common.tagged(*common.UNIT_TAGS)
class TestDiscovery(common.TransactionCase):
    def setUp(self) -> None:
        super().setUp()
        temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(temporary_directory.cleanup)
        self.root = Path(temporary_directory.name)
        sys.path.insert(0, str(self.root))
        self.addCleanup(sys.path.remove, str(self.root))
        self.package_name = f"discovery_probe_{uuid.uuid4().hex}"
        self.addCleanup(self._forget_package)
        self._write("__init__.py", "")

    def _forget_package(self) -> None:
        for module_name in [name for name in sys.modules if name.startswith(self.package_name)]:
            del sys.modules[module_name]

    def _write(self, relative_path: str, source: str) -> None:
        path = self.root / self.package_name / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(source, encoding="utf-8")

    def _expose(self) -> set[str]:
        package = importlib.import_module(self.package_name)
        return expose_subdirectory_tests(self.package_name, package.__path__)

    def test_exposes_nested_test_modules(self) -> None:
        self._write("unit/__init__.py", "")
        self._write("unit/test_alpha.py", "VALUE = 1\n")
        self._write("tour/__init__.py", "")
        self._write("tour/test_beta.py", "VALUE = 2\n")
        self._write("unit/helpers.py", "VALUE = 3\n")

        exposed = self._expose()

        self.assertEqual(exposed, {"test_alpha", "test_beta"})
        package = sys.modules[self.package_name]
        self.assertEqual(package.test_alpha.VALUE, 1)
        self.assertEqual(package.test_beta.VALUE, 2)

    def test_broken_test_module_fails_discovery(self) -> None:
        self._write("unit/__init__.py", "")
        self._write("unit/test_broken.py", "import discovery_probe_missing_dependency\n")

        with self.assertRaises(ImportError):
            self._expose()

    def test_broken_test_package_fails_discovery(self) -> None:
        self._write("unit/__init__.py", "import discovery_probe_missing_dependency\n")
        self._write("unit/test_hidden.py", "VALUE = 1\n")

        with self.assertRaises(ImportError):
            self._expose()

    def test_module_alias_skips_only_an_absent_module(self) -> None:
        importlib.import_module(self.package_name)

        self.assertFalse(expose_module_alias(self.package_name, "absent", "test_absent", warn_on_missing=False))

        self._write("present.py", "import discovery_probe_missing_dependency\n")
        with self.assertRaises(ImportError):
            expose_module_alias(self.package_name, "present", "test_present", warn_on_missing=False)
