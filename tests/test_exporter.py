from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING
from typing import Any
from typing import Iterator

import pytest

from cleo.io.buffered_io import BufferedIO
from poetry.core.packages.dependency import Dependency
from poetry.core.toml.file import TOMLFile
from poetry.core.version.markers import parse_marker
from poetry.factory import Factory
from poetry.packages import Locker as BaseLocker
from poetry.repositories.legacy_repository import LegacyRepository


try:
    from poetry.core.packages.dependency_group import MAIN_GROUP
except ImportError:
    MAIN_GROUP = "default"

from poetry_plugin_export.exporter import Exporter
from tests.markers import MARKER_PY
from tests.markers import MARKER_PY27
from tests.markers import MARKER_PY36
from tests.markers import MARKER_PY36_38
from tests.markers import MARKER_PY36_ONLY
from tests.markers import MARKER_PY37
from tests.markers import MARKER_PY37_PY400
from tests.markers import MARKER_PY_DARWIN
from tests.markers import MARKER_PY_LINUX
from tests.markers import MARKER_PY_WIN32
from tests.markers import MARKER_PY_WINDOWS
from tests.markers import MARKER_WIN32
from tests.markers import MARKER_WINDOWS


if TYPE_CHECKING:
    from poetry.poetry import Poetry
    from pytest_mock import MockerFixture

    from tests.conftest import Config
    from tests.types import FixtureDirGetter


class Locker(BaseLocker):
    def __init__(self) -> None:
        self._lock = TOMLFile(Path.cwd().joinpath("poetry.lock"))
        self._locked = True
        self._content_hash = self._get_content_hash()

    def locked(self, is_locked: bool = True) -> Locker:
        self._locked = is_locked

        return self

    def mock_lock_data(self, data: dict[str, Any]) -> None:
        self._lock_data = data  # type: ignore[assignment]

    def is_locked(self) -> bool:
        return self._locked

    def is_fresh(self) -> bool:
        return True

    def _get_content_hash(self) -> str:
        return "123456789"


@pytest.fixture
def working_directory() -> Path:
    return Path(__file__).parent.parent


@pytest.fixture(autouse=True)
def mock_path_cwd(
    mocker: MockerFixture, working_directory: Path
) -> Iterator[MockerFixture]:
    yield mocker.patch("pathlib.Path.cwd", return_value=working_directory)


@pytest.fixture()
def locker() -> Locker:
    return Locker()


@pytest.fixture
def poetry(fixture_dir: FixtureDirGetter, locker: Locker) -> Poetry:
    p = Factory().create_poetry(fixture_dir("sample_project"))
    p._locker = locker

    return p


def set_package_requires(poetry: Poetry, skip: set[str] | None = None) -> None:
    skip = skip or set()
    packages = poetry.locker.locked_repository().packages
    package = poetry.package.with_dependency_groups([], only=True)
    for pkg in packages:
        if pkg.name not in skip:
            dep = pkg.to_dependency()
            if pkg.category == "dev":
                dep._groups = frozenset(["dev"])
            package.add_dependency(dep)

    poetry._package = package


def test_exporter_can_export_requirements_txt_with_standard_packages(
    tmp_dir: str, poetry: Poetry
) -> None:
    poetry.locker.mock_lock_data(  # type: ignore[attr-defined]
        {
            "package": [
                {
                    "name": "foo",
                    "version": "1.2.3",
                    "category": "main",
                    "optional": False,
                    "python-versions": "*",
                },
                {
                    "name": "bar",
                    "version": "4.5.6",
                    "category": "main",
                    "optional": False,
                    "python-versions": "*",
                },
            ],
            "metadata": {
                "python-versions": "*",
                "content-hash": "123456789",
                "hashes": {"foo": [], "bar": []},
            },
        }
    )
    set_package_requires(poetry)

    exporter = Exporter(poetry)
    exporter.export("requirements.txt", Path(tmp_dir), "requirements.txt")

    with (Path(tmp_dir) / "requirements.txt").open(encoding="utf-8") as f:
        content = f.read()

    expected = f"""\
bar==4.5.6 ; {MARKER_PY}
foo==1.2.3 ; {MARKER_PY}
"""

    assert content == expected


def test_exporter_can_export_requirements_txt_with_standard_packages_and_markers(
    tmp_dir: str, poetry: Poetry
) -> None:
    poetry.locker.mock_lock_data(  # type: ignore[attr-defined]
        {
            "package": [
                {
                    "name": "foo",
                    "version": "1.2.3",
                    "category": "main",
                    "optional": False,
                    "python-versions": "*",
                    "marker": "python_version < '3.7'",
                },
                {
                    "name": "bar",
                    "version": "4.5.6",
                    "category": "main",
                    "optional": False,
                    "python-versions": "*",
                    "marker": "extra =='foo'",
                },
                {
                    "name": "baz",
                    "version": "7.8.9",
                    "category": "main",
                    "optional": False,
                    "python-versions": "*",
                    "marker": "sys_platform == 'win32'",
                },
            ],
            "metadata": {
                "python-versions": "*",
                "content-hash": "123456789",
                "hashes": {"foo": [], "bar": [], "baz": []},
            },
        }
    )
    set_package_requires(poetry)

    exporter = Exporter(poetry)
    exporter.export("requirements.txt", Path(tmp_dir), "requirements.txt")

    with (Path(tmp_dir) / "requirements.txt").open(encoding="utf-8") as f:
        content = f.read()

    expected = f"""\
bar==4.5.6 ; {MARKER_PY}
baz==7.8.9 ; {MARKER_PY_WIN32}
foo==1.2.3 ; {MARKER_PY27.union(MARKER_PY36_ONLY)}
"""

    assert content == expected


def test_exporter_can_export_requirements_txt_poetry(
    tmp_dir: str, poetry: Poetry
) -> None:
    """Regression test for #3254"""

    poetry.locker.mock_lock_data(  # type: ignore[attr-defined]
        {
            "package": [
                {
                    "name": "poetry",
                    "version": "1.1.4",
                    "category": "main",
                    "optional": False,
                    "python-versions": "*",
                    "dependencies": {"keyring": "*"},
                },
                {
                    "name": "junit-xml",
                    "version": "1.9",
                    "category": "main",
                    "optional": False,
                    "python-versions": "*",
                    "dependencies": {"six": "*"},
                },
                {
                    "name": "keyring",
                    "version": "21.8.0",
                    "category": "main",
                    "optional": False,
                    "python-versions": "*",
                    "dependencies": {
                        "SecretStorage": {
                            "version": "*",
                            "markers": "sys_platform == 'linux'",
                        }
                    },
                },
                {
                    "name": "secretstorage",
                    "version": "3.3.0",
                    "category": "main",
                    "optional": False,
                    "python-versions": "*",
                    "dependencies": {"cryptography": "*"},
                },
                {
                    "name": "cryptography",
                    "version": "3.2",
                    "category": "main",
                    "optional": False,
                    "python-versions": "*",
                    "dependencies": {"six": "*"},
                },
                {
                    "name": "six",
                    "version": "1.15.0",
                    "category": "main",
                    "optional": False,
                    "python-versions": "*",
                },
            ],
            "metadata": {
                "python-versions": "*",
                "content-hash": "123456789",
                "hashes": {
                    "poetry": [],
                    "keyring": [],
                    "secretstorage": [],
                    "cryptography": [],
                    "six": [],
                    "junit-xml": [],
                },
            },
        }
    )
    set_package_requires(
        poetry, skip={"keyring", "secretstorage", "cryptography", "six"}
    )

    exporter = Exporter(poetry)
    exporter.export("requirements.txt", Path(tmp_dir), "requirements.txt")

    with (Path(tmp_dir) / "requirements.txt").open(encoding="utf-8") as f:
        content = f.read()

    # The dependency graph:
    # junit-xml 1.9 Creates JUnit XML test result documents that can be read by tools
    # └── six *     such as Jenkins
    # poetry 1.1.4 Python dependency management and packaging made easy.
    # ├── keyring >=21.2.0,<22.0.0
    # │   ├── importlib-metadata >=1
    # │   │   └── zipp >=0.5
    # │   ├── jeepney >=0.4.2
    # │   ├── pywin32-ctypes <0.1.0 || >0.1.0,<0.1.1 || >0.1.1
    # │   └── secretstorage >=3.2 -- On linux only
    # │       ├── cryptography >=2.0
    # │       │   └── six >=1.4.1
    # │       └── jeepney >=0.6 (circular dependency aborted here)
    expected = {
        "poetry": Dependency.create_from_pep_508(f"poetry==1.1.4; {MARKER_PY}"),
        "junit-xml": Dependency.create_from_pep_508(f"junit-xml==1.9 ; {MARKER_PY}"),
        "keyring": Dependency.create_from_pep_508(f"keyring==21.8.0 ; {MARKER_PY}"),
        "secretstorage": Dependency.create_from_pep_508(
            f"secretstorage==3.3.0 ; {MARKER_PY_LINUX}"
        ),
        "cryptography": Dependency.create_from_pep_508(
            f"cryptography==3.2 ; {MARKER_PY_LINUX}"
        ),
        "six": Dependency.create_from_pep_508(
            f"six==1.15.0 ; {MARKER_PY.union(MARKER_PY_LINUX)}"
        ),
    }

    for line in content.strip().split("\n"):
        dependency = Dependency.create_from_pep_508(line)
        assert dependency.name in expected
        expected_dependency = expected.pop(dependency.name)
        assert dependency == expected_dependency
        assert dependency.marker == expected_dependency.marker


def test_exporter_can_export_requirements_txt_pyinstaller(
    tmp_dir: str, poetry: Poetry
) -> None:
    """Regression test for #3254"""

    poetry.locker.mock_lock_data(  # type: ignore[attr-defined]
        {
            "package": [
                {
                    "name": "pyinstaller",
                    "version": "4.0",
                    "category": "main",
                    "optional": False,
                    "python-versions": "*",
                    "dependencies": {
                        "altgraph": "*",
                        "macholib": {
                            "version": "*",
                            "markers": "sys_platform == 'darwin'",
                        },
                    },
                },
                {
                    "name": "altgraph",
                    "version": "0.17",
                    "category": "main",
                    "optional": False,
                    "python-versions": "*",
                },
                {
                    "name": "macholib",
                    "version": "1.8",
                    "category": "main",
                    "optional": False,
                    "python-versions": "*",
                    "dependencies": {"altgraph": ">=0.15"},
                },
            ],
            "metadata": {
                "python-versions": "*",
                "content-hash": "123456789",
                "hashes": {"pyinstaller": [], "altgraph": [], "macholib": []},
            },
        }
    )
    set_package_requires(poetry, skip={"altgraph", "macholib"})

    exporter = Exporter(poetry)
    exporter.export("requirements.txt", Path(tmp_dir), "requirements.txt")

    with (Path(tmp_dir) / "requirements.txt").open(encoding="utf-8") as f:
        content = f.read()

    # Rationale for the results:
    #  * PyInstaller has an explicit dependency on altgraph, so it must always be
    #    installed.
    #  * PyInstaller requires macholib on Darwin, which in turn requires altgraph.
    # The dependency graph:
    # pyinstaller 4.0     PyInstaller bundles a Python application and all its
    # ├── altgraph *      dependencies into a single package.
    # ├── macholib >=1.8 -- only on Darwin
    # │   └── altgraph >=0.15
    expected = {
        "pyinstaller": Dependency.create_from_pep_508(
            f"pyinstaller==4.0 ; {MARKER_PY}"
        ),
        "altgraph": Dependency.create_from_pep_508(
            f"altgraph==0.17 ; {MARKER_PY.union(MARKER_PY_DARWIN)}"
        ),
        "macholib": Dependency.create_from_pep_508(
            f"macholib==1.8 ; {MARKER_PY_DARWIN}"
        ),
    }

    for line in content.strip().split("\n"):
        dependency = Dependency.create_from_pep_508(line)
        assert dependency.name in expected
        expected_dependency = expected.pop(dependency.name)
        assert dependency == expected_dependency
        assert dependency.marker == expected_dependency.marker


def test_exporter_can_export_requirements_txt_with_nested_packages_and_markers(
    tmp_dir: str, poetry: Poetry
) -> None:
    poetry.locker.mock_lock_data(  # type: ignore[attr-defined]
        {
            "package": [
                {
                    "name": "a",
                    "version": "1.2.3",
                    "category": "main",
                    "optional": False,
                    "python-versions": "*",
                    "marker": "python_version < '3.7'",
                    "dependencies": {"b": ">=0.0.0", "c": ">=0.0.0"},
                },
                {
                    "name": "b",
                    "version": "4.5.6",
                    "category": "main",
                    "optional": False,
                    "python-versions": "*",
                    "marker": "platform_system == 'Windows'",
                    "dependencies": {"d": ">=0.0.0"},
                },
                {
                    "name": "c",
                    "version": "7.8.9",
                    "category": "main",
                    "optional": False,
                    "python-versions": "*",
                    "marker": "sys_platform == 'win32'",
                    "dependencies": {"d": ">=0.0.0"},
                },
                {
                    "name": "d",
                    "version": "0.0.1",
                    "category": "main",
                    "optional": False,
                    "python-versions": "*",
                },
            ],
            "metadata": {
                "python-versions": "*",
                "content-hash": "123456789",
                "hashes": {"a": [], "b": [], "c": [], "d": []},
            },
        }
    )
    set_package_requires(poetry, skip={"b", "c", "d"})

    exporter = Exporter(poetry)
    exporter.export("requirements.txt", Path(tmp_dir), "requirements.txt")

    with (Path(tmp_dir) / "requirements.txt").open(encoding="utf-8") as f:
        content = f.read()

    marker_py = MARKER_PY27.union(MARKER_PY36_ONLY)
    marker_py_win32 = marker_py.intersect(MARKER_WIN32)
    marker_py_windows = marker_py.intersect(MARKER_WINDOWS)

    expected = {
        "a": Dependency.create_from_pep_508(f"a==1.2.3 ; {marker_py}"),
        "b": Dependency.create_from_pep_508(f"b==4.5.6 ; {marker_py_windows}"),
        "c": Dependency.create_from_pep_508(f"c==7.8.9 ; {marker_py_win32}"),
        "d": Dependency.create_from_pep_508(
            f"d==0.0.1 ; {marker_py_win32.union(marker_py_windows)}"
        ),
    }

    for line in content.strip().split("\n"):
        dependency = Dependency.create_from_pep_508(line)
        assert dependency.name in expected
        expected_dependency = expected.pop(dependency.name)
        assert dependency == expected_dependency
        assert dependency.marker == expected_dependency.marker

    assert expected == {}


@pytest.mark.parametrize(
    ["dev", "lines"],
    [
        (
            False,
            [f"a==1.2.3 ; {MARKER_PY27.union(MARKER_PY36_38)}"],
        ),
        (
            True,
            [
                f"a==1.2.3 ; {MARKER_PY27.union(MARKER_PY36_38).union(MARKER_PY36)}",
                f"b==4.5.6 ; {MARKER_PY}",
            ],
        ),
    ],
)
def test_exporter_can_export_requirements_txt_with_nested_packages_and_markers_any(
    tmp_dir: str, poetry: Poetry, dev: bool, lines: list[str]
) -> None:
    poetry.locker.mock_lock_data(  # type: ignore[attr-defined]
        {
            "package": [
                {
                    "name": "a",
                    "version": "1.2.3",
                    "category": "main",
                    "optional": False,
                    "python-versions": "*",
                },
                {
                    "name": "b",
                    "version": "4.5.6",
                    "category": "dev",
                    "optional": False,
                    "python-versions": "*",
                    "dependencies": {"a": ">=1.2.3"},
                },
            ],
            "metadata": {
                "python-versions": "*",
                "content-hash": "123456789",
                "hashes": {"a": [], "b": []},
            },
        }
    )

    root = poetry.package.with_dependency_groups([], only=True)
    root.add_dependency(
        Factory.create_dependency(
            name="a", constraint={"version": "^1.2.3", "python": "<3.8"}
        )
    )
    root.add_dependency(
        Factory.create_dependency(
            name="b", constraint={"version": "^4.5.6"}, groups=["dev"]
        )
    )
    poetry._package = root

    exporter = Exporter(poetry)
    if dev:
        exporter.only_groups([MAIN_GROUP, "dev"])
    exporter.export("requirements.txt", Path(tmp_dir), "requirements.txt")

    with (Path(tmp_dir) / "requirements.txt").open(encoding="utf-8") as f:
        content = f.read()

    assert content.strip() == "\n".join(lines)


def test_exporter_can_export_requirements_txt_with_standard_packages_and_hashes(
    tmp_dir: str, poetry: Poetry
) -> None:
    poetry.locker.mock_lock_data(  # type: ignore[attr-defined]
        {
            "package": [
                {
                    "name": "foo",
                    "version": "1.2.3",
                    "category": "main",
                    "optional": False,
                    "python-versions": "*",
                },
                {
                    "name": "bar",
                    "version": "4.5.6",
                    "category": "main",
                    "optional": False,
                    "python-versions": "*",
                },
            ],
            "metadata": {
                "python-versions": "*",
                "content-hash": "123456789",
                "hashes": {"foo": ["12345"], "bar": ["67890"]},
            },
        }
    )
    set_package_requires(poetry)

    exporter = Exporter(poetry)
    exporter.export("requirements.txt", Path(tmp_dir), "requirements.txt")

    with (Path(tmp_dir) / "requirements.txt").open(encoding="utf-8") as f:
        content = f.read()

    expected = f"""\
bar==4.5.6 ; {MARKER_PY} \\
    --hash=sha256:67890
foo==1.2.3 ; {MARKER_PY} \\
    --hash=sha256:12345
"""

    assert content == expected


def test_exporter_can_export_requirements_txt_with_standard_packages_and_sorted_hashes(
    tmp_dir: str, poetry: Poetry
) -> None:
    poetry.locker.mock_lock_data(  # type: ignore[attr-defined]
        {
            "package": [
                {
                    "name": "foo",
                    "version": "1.2.3",
                    "category": "main",
                    "optional": False,
                    "python-versions": "*",
                },
                {
                    "name": "bar",
                    "version": "4.5.6",
                    "category": "main",
                    "optional": False,
                    "python-versions": "*",
                },
            ],
            "metadata": {
                "python-versions": "*",
                "content-hash": "123456789",
                "hashes": {"foo": ["67890", "12345"], "bar": ["67890", "12345"]},
            },
        }
    )
    set_package_requires(poetry)

    exporter = Exporter(poetry)
    exporter.export("requirements.txt", Path(tmp_dir), "requirements.txt")

    with (Path(tmp_dir) / "requirements.txt").open(encoding="utf-8") as f:
        content = f.read()

    expected = f"""\
bar==4.5.6 ; {MARKER_PY} \\
    --hash=sha256:12345 \\
    --hash=sha256:67890
foo==1.2.3 ; {MARKER_PY} \\
    --hash=sha256:12345 \\
    --hash=sha256:67890
"""

    assert content == expected


def test_exporter_requirements_txt_with_standard_packages_and_hashes_disabled(
    tmp_dir: str, poetry: Poetry
) -> None:
    poetry.locker.mock_lock_data(  # type: ignore[attr-defined]
        {
            "package": [
                {
                    "name": "foo",
                    "version": "1.2.3",
                    "category": "main",
                    "optional": False,
                    "python-versions": "*",
                },
                {
                    "name": "bar",
                    "version": "4.5.6",
                    "category": "main",
                    "optional": False,
                    "python-versions": "*",
                },
            ],
            "metadata": {
                "python-versions": "*",
                "content-hash": "123456789",
                "hashes": {"foo": ["12345"], "bar": ["67890"]},
            },
        }
    )
    set_package_requires(poetry)

    exporter = Exporter(poetry)
    exporter.with_hashes(False)
    exporter.export("requirements.txt", Path(tmp_dir), "requirements.txt")

    with (Path(tmp_dir) / "requirements.txt").open(encoding="utf-8") as f:
        content = f.read()

    expected = f"""\
bar==4.5.6 ; {MARKER_PY}
foo==1.2.3 ; {MARKER_PY}
"""

    assert content == expected


def test_exporter_exports_requirements_txt_without_dev_packages_by_default(
    tmp_dir: str, poetry: Poetry
) -> None:
    poetry.locker.mock_lock_data(  # type: ignore[attr-defined]
        {
            "package": [
                {
                    "name": "foo",
                    "version": "1.2.3",
                    "category": "main",
                    "optional": False,
                    "python-versions": "*",
                },
                {
                    "name": "bar",
                    "version": "4.5.6",
                    "category": "dev",
                    "optional": False,
                    "python-versions": "*",
                },
            ],
            "metadata": {
                "python-versions": "*",
                "content-hash": "123456789",
                "hashes": {"foo": ["12345"], "bar": ["67890"]},
            },
        }
    )
    set_package_requires(poetry)

    exporter = Exporter(poetry)
    exporter.export("requirements.txt", Path(tmp_dir), "requirements.txt")

    with (Path(tmp_dir) / "requirements.txt").open(encoding="utf-8") as f:
        content = f.read()

    expected = f"""\
foo==1.2.3 ; {MARKER_PY} \\
    --hash=sha256:12345
"""

    assert content == expected


def test_exporter_exports_requirements_txt_with_dev_packages_if_opted_in(
    tmp_dir: str, poetry: Poetry
) -> None:
    poetry.locker.mock_lock_data(  # type: ignore[attr-defined]
        {
            "package": [
                {
                    "name": "foo",
                    "version": "1.2.3",
                    "category": "main",
                    "optional": False,
                    "python-versions": "*",
                },
                {
                    "name": "bar",
                    "version": "4.5.6",
                    "category": "dev",
                    "optional": False,
                    "python-versions": "*",
                },
            ],
            "metadata": {
                "python-versions": "*",
                "content-hash": "123456789",
                "hashes": {"foo": ["12345"], "bar": ["67890"]},
            },
        }
    )
    set_package_requires(poetry)

    exporter = Exporter(poetry)
    exporter.only_groups([MAIN_GROUP, "dev"])
    exporter.export("requirements.txt", Path(tmp_dir), "requirements.txt")

    with (Path(tmp_dir) / "requirements.txt").open(encoding="utf-8") as f:
        content = f.read()

    expected = f"""\
bar==4.5.6 ; {MARKER_PY} \\
    --hash=sha256:67890
foo==1.2.3 ; {MARKER_PY} \\
    --hash=sha256:12345
"""

    assert content == expected


def test_exporter_exports_requirements_txt_without_groups_if_set_explicity(
    tmp_dir: str, poetry: Poetry
) -> None:
    poetry.locker.mock_lock_data(  # type: ignore[attr-defined]
        {
            "package": [
                {
                    "name": "foo",
                    "version": "1.2.3",
                    "category": "main",
                    "optional": False,
                    "python-versions": "*",
                },
                {
                    "name": "bar",
                    "version": "4.5.6",
                    "category": "dev",
                    "optional": False,
                    "python-versions": "*",
                },
            ],
            "metadata": {
                "python-versions": "*",
                "content-hash": "123456789",
                "hashes": {"foo": ["12345"], "bar": ["67890"]},
            },
        }
    )
    set_package_requires(poetry)

    exporter = Exporter(poetry)
    exporter.only_groups([])
    exporter.export("requirements.txt", Path(tmp_dir), "requirements.txt")

    with (Path(tmp_dir) / "requirements.txt").open(encoding="utf-8") as f:
        content = f.read()

    assert content == "\n"


def test_exporter_exports_requirements_txt_without_optional_packages(
    tmp_dir: str, poetry: Poetry
) -> None:
    poetry.locker.mock_lock_data(  # type: ignore[attr-defined]
        {
            "package": [
                {
                    "name": "foo",
                    "version": "1.2.3",
                    "category": "main",
                    "optional": False,
                    "python-versions": "*",
                },
                {
                    "name": "bar",
                    "version": "4.5.6",
                    "category": "dev",
                    "optional": True,
                    "python-versions": "*",
                },
            ],
            "metadata": {
                "python-versions": "*",
                "content-hash": "123456789",
                "hashes": {"foo": ["12345"], "bar": ["67890"]},
            },
        }
    )
    set_package_requires(poetry)

    exporter = Exporter(poetry)
    exporter.only_groups([MAIN_GROUP, "dev"])
    exporter.export("requirements.txt", Path(tmp_dir), "requirements.txt")

    with (Path(tmp_dir) / "requirements.txt").open(encoding="utf-8") as f:
        content = f.read()

    expected = f"""\
foo==1.2.3 ; {MARKER_PY} \\
    --hash=sha256:12345
"""

    assert content == expected


@pytest.mark.parametrize(
    ["extras", "lines"],
    [
        (
            None,
            [f"foo==1.2.3 ; {MARKER_PY}"],
        ),
        (
            False,
            [f"foo==1.2.3 ; {MARKER_PY}"],
        ),
        (
            True,
            [
                f"bar==4.5.6 ; {MARKER_PY}",
                f"foo==1.2.3 ; {MARKER_PY}",
                f"spam==0.1.0 ; {MARKER_PY}",
            ],
        ),
        (
            ["feature_bar"],
            [
                f"bar==4.5.6 ; {MARKER_PY}",
                f"foo==1.2.3 ; {MARKER_PY}",
                f"spam==0.1.0 ; {MARKER_PY}",
            ],
        ),
    ],
)
def test_exporter_exports_requirements_txt_with_optional_packages(
    tmp_dir: str,
    poetry: Poetry,
    extras: bool | list[str] | None,
    lines: list[str],
) -> None:
    poetry.locker.mock_lock_data(  # type: ignore[attr-defined]
        {
            "package": [
                {
                    "name": "foo",
                    "version": "1.2.3",
                    "category": "main",
                    "optional": False,
                    "python-versions": "*",
                },
                {
                    "name": "bar",
                    "version": "4.5.6",
                    "category": "main",
                    "optional": True,
                    "python-versions": "*",
                    "dependencies": {"spam": ">=0.1"},
                },
                {
                    "name": "spam",
                    "version": "0.1.0",
                    "category": "main",
                    "optional": True,
                    "python-versions": "*",
                },
            ],
            "metadata": {
                "python-versions": "*",
                "content-hash": "123456789",
                "hashes": {"foo": ["12345"], "bar": ["67890"], "spam": ["abcde"]},
            },
            "extras": {"feature_bar": ["bar"]},
        }
    )
    set_package_requires(poetry)

    exporter = Exporter(poetry)
    exporter.only_groups([MAIN_GROUP, "dev"])
    exporter.with_hashes(False)
    exporter.with_extras(extras)
    exporter.export(
        "requirements.txt",
        Path(tmp_dir),
        "requirements.txt",
    )

    with (Path(tmp_dir) / "requirements.txt").open(encoding="utf-8") as f:
        content = f.read()

    expected = "\n".join(lines)

    assert content.strip() == expected


def test_exporter_can_export_requirements_txt_with_git_packages(
    tmp_dir: str, poetry: Poetry
) -> None:
    poetry.locker.mock_lock_data(  # type: ignore[attr-defined]
        {
            "package": [
                {
                    "name": "foo",
                    "version": "1.2.3",
                    "category": "main",
                    "optional": False,
                    "python-versions": "*",
                    "source": {
                        "type": "git",
                        "url": "https://github.com/foo/foo.git",
                        "reference": "123456",
                    },
                }
            ],
            "metadata": {
                "python-versions": "*",
                "content-hash": "123456789",
                "hashes": {"foo": []},
            },
        }
    )
    set_package_requires(poetry)

    exporter = Exporter(poetry)
    exporter.export("requirements.txt", Path(tmp_dir), "requirements.txt")

    with (Path(tmp_dir) / "requirements.txt").open(encoding="utf-8") as f:
        content = f.read()

    expected = f"""\
foo @ git+https://github.com/foo/foo.git@123456 ; {MARKER_PY}
"""

    assert content == expected


def test_exporter_can_export_requirements_txt_with_nested_packages(
    tmp_dir: str, poetry: Poetry
) -> None:
    poetry.locker.mock_lock_data(  # type: ignore[attr-defined]
        {
            "package": [
                {
                    "name": "foo",
                    "version": "1.2.3",
                    "category": "main",
                    "optional": False,
                    "python-versions": "*",
                    "source": {
                        "type": "git",
                        "url": "https://github.com/foo/foo.git",
                        "reference": "123456",
                    },
                },
                {
                    "name": "bar",
                    "version": "4.5.6",
                    "category": "main",
                    "optional": False,
                    "python-versions": "*",
                    "dependencies": {
                        "foo": {
                            "git": "https://github.com/foo/foo.git",
                            "rev": "123456",
                        }
                    },
                },
            ],
            "metadata": {
                "python-versions": "*",
                "content-hash": "123456789",
                "hashes": {"foo": [], "bar": []},
            },
        }
    )
    set_package_requires(poetry, skip={"foo"})

    exporter = Exporter(poetry)
    exporter.export("requirements.txt", Path(tmp_dir), "requirements.txt")

    with (Path(tmp_dir) / "requirements.txt").open(encoding="utf-8") as f:
        content = f.read()

    expected = f"""\
bar==4.5.6 ; {MARKER_PY}
foo @ git+https://github.com/foo/foo.git@123456 ; {MARKER_PY}
"""

    assert content == expected


def test_exporter_can_export_requirements_txt_with_nested_packages_cyclic(
    tmp_dir: str, poetry: Poetry
) -> None:
    poetry.locker.mock_lock_data(  # type: ignore[attr-defined]
        {
            "package": [
                {
                    "name": "foo",
                    "version": "1.2.3",
                    "category": "main",
                    "optional": False,
                    "python-versions": "*",
                    "dependencies": {"bar": {"version": "4.5.6"}},
                },
                {
                    "name": "bar",
                    "version": "4.5.6",
                    "category": "main",
                    "optional": False,
                    "python-versions": "*",
                    "dependencies": {"baz": {"version": "7.8.9"}},
                },
                {
                    "name": "baz",
                    "version": "7.8.9",
                    "category": "main",
                    "optional": False,
                    "python-versions": "*",
                    "dependencies": {"foo": {"version": "1.2.3"}},
                },
            ],
            "metadata": {
                "python-versions": "*",
                "content-hash": "123456789",
                "hashes": {"foo": [], "bar": [], "baz": []},
            },
        }
    )
    set_package_requires(poetry, skip={"bar", "baz"})

    exporter = Exporter(poetry)
    exporter.export("requirements.txt", Path(tmp_dir), "requirements.txt")

    with (Path(tmp_dir) / "requirements.txt").open(encoding="utf-8") as f:
        content = f.read()

    expected = f"""\
bar==4.5.6 ; {MARKER_PY}
baz==7.8.9 ; {MARKER_PY}
foo==1.2.3 ; {MARKER_PY}
"""

    assert content == expected


def test_exporter_can_export_requirements_txt_with_nested_packages_and_multiple_markers(
    tmp_dir: str, poetry: Poetry
) -> None:
    poetry.locker.mock_lock_data(  # type: ignore[attr-defined]
        {
            "package": [
                {
                    "name": "foo",
                    "version": "1.2.3",
                    "category": "main",
                    "optional": False,
                    "python-versions": "*",
                    "dependencies": {
                        "bar": [
                            {
                                "version": ">=1.2.3,<7.8.10",
                                "markers": 'platform_system != "Windows"',
                            },
                            {
                                "version": ">=4.5.6,<7.8.10",
                                "markers": 'platform_system == "Windows"',
                            },
                        ]
                    },
                },
                {
                    "name": "bar",
                    "version": "7.8.9",
                    "category": "main",
                    "optional": True,
                    "python-versions": "*",
                    "dependencies": {
                        "baz": {
                            "version": "!=10.11.12",
                            "markers": 'platform_system == "Windows"',
                        }
                    },
                },
                {
                    "name": "baz",
                    "version": "10.11.13",
                    "category": "main",
                    "optional": True,
                    "python-versions": "*",
                },
            ],
            "metadata": {
                "python-versions": "*",
                "content-hash": "123456789",
                "hashes": {"foo": [], "bar": [], "baz": []},
            },
        }
    )
    set_package_requires(poetry)

    exporter = Exporter(poetry)
    exporter.with_hashes(False)
    exporter.export("requirements.txt", Path(tmp_dir), "requirements.txt")

    with (Path(tmp_dir) / "requirements.txt").open(encoding="utf-8") as f:
        content = f.read()

    marker_py_not_windows = MARKER_PY.intersect(
        parse_marker('platform_system != "Windows"')
    )
    expected = f"""\
bar==7.8.9 ; {marker_py_not_windows.union(MARKER_PY_WINDOWS)}
baz==10.11.13 ; {MARKER_PY_WINDOWS}
foo==1.2.3 ; {MARKER_PY}
"""

    assert content == expected


def test_exporter_can_export_requirements_txt_with_git_packages_and_markers(
    tmp_dir: str, poetry: Poetry
) -> None:
    poetry.locker.mock_lock_data(  # type: ignore[attr-defined]
        {
            "package": [
                {
                    "name": "foo",
                    "version": "1.2.3",
                    "category": "main",
                    "optional": False,
                    "python-versions": "*",
                    "marker": "python_version < '3.7'",
                    "source": {
                        "type": "git",
                        "url": "https://github.com/foo/foo.git",
                        "reference": "123456",
                    },
                }
            ],
            "metadata": {
                "python-versions": "*",
                "content-hash": "123456789",
                "hashes": {"foo": []},
            },
        }
    )
    set_package_requires(poetry)

    exporter = Exporter(poetry)
    exporter.export("requirements.txt", Path(tmp_dir), "requirements.txt")

    with (Path(tmp_dir) / "requirements.txt").open(encoding="utf-8") as f:
        content = f.read()

    expected = f"""\
foo @ git+https://github.com/foo/foo.git@123456 ; {MARKER_PY27.union(MARKER_PY36_ONLY)}
"""

    assert content == expected


def test_exporter_can_export_requirements_txt_with_directory_packages(
    tmp_dir: str, poetry: Poetry, working_directory: Path
) -> None:
    poetry.locker.mock_lock_data(  # type: ignore[attr-defined]
        {
            "package": [
                {
                    "name": "foo",
                    "version": "1.2.3",
                    "category": "main",
                    "optional": False,
                    "python-versions": "*",
                    "source": {
                        "type": "directory",
                        "url": "tests/fixtures/sample_project",
                        "reference": "",
                    },
                }
            ],
            "metadata": {
                "python-versions": "*",
                "content-hash": "123456789",
                "hashes": {"foo": []},
            },
        }
    )
    set_package_requires(poetry)

    exporter = Exporter(poetry)
    exporter.export("requirements.txt", Path(tmp_dir), "requirements.txt")

    with (Path(tmp_dir) / "requirements.txt").open(encoding="utf-8") as f:
        content = f.read()

    expected = f"""\
foo @ {working_directory.as_uri()}/tests/fixtures/sample_project ; {MARKER_PY}
"""

    assert content == expected


def test_exporter_can_export_requirements_txt_with_nested_directory_packages(
    tmp_dir: str, poetry: Poetry, working_directory: Path
) -> None:
    poetry.locker.mock_lock_data(  # type: ignore[attr-defined]
        {
            "package": [
                {
                    "name": "foo",
                    "version": "1.2.3",
                    "category": "main",
                    "optional": False,
                    "python-versions": "*",
                    "source": {
                        "type": "directory",
                        "url": "tests/fixtures/sample_project",
                        "reference": "",
                    },
                },
                {
                    "name": "bar",
                    "version": "4.5.6",
                    "category": "main",
                    "optional": False,
                    "python-versions": "*",
                    "source": {
                        "type": "directory",
                        "url": (
                            "tests/fixtures/sample_project/"
                            "../project_with_nested_local/bar"
                        ),
                        "reference": "",
                    },
                },
                {
                    "name": "baz",
                    "version": "7.8.9",
                    "category": "main",
                    "optional": False,
                    "python-versions": "*",
                    "source": {
                        "type": "directory",
                        "url": (
                            "tests/fixtures/sample_project/"
                            "../project_with_nested_local/bar/.."
                        ),
                        "reference": "",
                    },
                },
            ],
            "metadata": {
                "python-versions": "*",
                "content-hash": "123456789",
                "hashes": {"foo": [], "bar": [], "baz": []},
            },
        }
    )
    set_package_requires(poetry)

    exporter = Exporter(poetry)
    exporter.export("requirements.txt", Path(tmp_dir), "requirements.txt")

    with (Path(tmp_dir) / "requirements.txt").open(encoding="utf-8") as f:
        content = f.read()

    root_uri = f"{working_directory.as_uri()}/tests/fixtures"
    expected = f"""\
bar @ {root_uri}/project_with_nested_local/bar ; {MARKER_PY}
baz @ {root_uri}/project_with_nested_local ; {MARKER_PY}
foo @ {root_uri}/sample_project ; {MARKER_PY}
"""

    assert content == expected


def test_exporter_can_export_requirements_txt_with_directory_packages_and_markers(
    tmp_dir: str, poetry: Poetry, working_directory: Path
) -> None:
    poetry.locker.mock_lock_data(  # type: ignore[attr-defined]
        {
            "package": [
                {
                    "name": "foo",
                    "version": "1.2.3",
                    "category": "main",
                    "optional": False,
                    "python-versions": "*",
                    "marker": "python_version < '3.7'",
                    "source": {
                        "type": "directory",
                        "url": "tests/fixtures/sample_project",
                        "reference": "",
                    },
                }
            ],
            "metadata": {
                "python-versions": "*",
                "content-hash": "123456789",
                "hashes": {"foo": []},
            },
        }
    )
    set_package_requires(poetry)

    exporter = Exporter(poetry)
    exporter.export("requirements.txt", Path(tmp_dir), "requirements.txt")

    with (Path(tmp_dir) / "requirements.txt").open(encoding="utf-8") as f:
        content = f.read()

    expected = f"""\
foo @ {working_directory.as_uri()}/tests/fixtures/sample_project ;\
 {MARKER_PY27.union(MARKER_PY36_ONLY)}
"""

    assert content == expected


def test_exporter_can_export_requirements_txt_with_file_packages(
    tmp_dir: str, poetry: Poetry, working_directory: Path
) -> None:
    poetry.locker.mock_lock_data(  # type: ignore[attr-defined]
        {
            "package": [
                {
                    "name": "foo",
                    "version": "1.2.3",
                    "category": "main",
                    "optional": False,
                    "python-versions": "*",
                    "source": {
                        "type": "file",
                        "url": "tests/fixtures/distributions/demo-0.1.0.tar.gz",
                        "reference": "",
                    },
                }
            ],
            "metadata": {
                "python-versions": "*",
                "content-hash": "123456789",
                "hashes": {"foo": []},
            },
        }
    )
    set_package_requires(poetry)

    exporter = Exporter(poetry)
    exporter.export("requirements.txt", Path(tmp_dir), "requirements.txt")

    with (Path(tmp_dir) / "requirements.txt").open(encoding="utf-8") as f:
        content = f.read()

    expected = f"""\
foo @ {working_directory.as_uri()}/tests/fixtures/distributions/demo-0.1.0.tar.gz ;\
 {MARKER_PY}
"""

    assert content == expected


def test_exporter_can_export_requirements_txt_with_file_packages_and_markers(
    tmp_dir: str, poetry: Poetry, working_directory: Path
) -> None:
    poetry.locker.mock_lock_data(  # type: ignore[attr-defined]
        {
            "package": [
                {
                    "name": "foo",
                    "version": "1.2.3",
                    "category": "main",
                    "optional": False,
                    "python-versions": "*",
                    "marker": "python_version < '3.7'",
                    "source": {
                        "type": "file",
                        "url": "tests/fixtures/distributions/demo-0.1.0.tar.gz",
                        "reference": "",
                    },
                }
            ],
            "metadata": {
                "python-versions": "*",
                "content-hash": "123456789",
                "hashes": {"foo": []},
            },
        }
    )
    set_package_requires(poetry)

    exporter = Exporter(poetry)
    exporter.export("requirements.txt", Path(tmp_dir), "requirements.txt")

    with (Path(tmp_dir) / "requirements.txt").open(encoding="utf-8") as f:
        content = f.read()

    uri = f"{working_directory.as_uri()}/tests/fixtures/distributions/demo-0.1.0.tar.gz"
    expected = f"""\
foo @ {uri} ; {MARKER_PY27.union(MARKER_PY36_ONLY)}
"""

    assert content == expected


def test_exporter_exports_requirements_txt_with_legacy_packages(
    tmp_dir: str, poetry: Poetry
) -> None:
    poetry.pool.add_repository(
        LegacyRepository(
            "custom",
            "https://example.com/simple",
        )
    )
    poetry.locker.mock_lock_data(  # type: ignore[attr-defined]
        {
            "package": [
                {
                    "name": "foo",
                    "version": "1.2.3",
                    "category": "main",
                    "optional": False,
                    "python-versions": "*",
                },
                {
                    "name": "bar",
                    "version": "4.5.6",
                    "category": "dev",
                    "optional": False,
                    "python-versions": "*",
                    "source": {
                        "type": "legacy",
                        "url": "https://example.com/simple",
                        "reference": "",
                    },
                },
            ],
            "metadata": {
                "python-versions": "*",
                "content-hash": "123456789",
                "hashes": {"foo": ["12345"], "bar": ["67890"]},
            },
        }
    )
    set_package_requires(poetry)

    exporter = Exporter(poetry)
    exporter.only_groups([MAIN_GROUP, "dev"])
    exporter.export("requirements.txt", Path(tmp_dir), "requirements.txt")

    with (Path(tmp_dir) / "requirements.txt").open(encoding="utf-8") as f:
        content = f.read()

    expected = f"""\
--extra-index-url https://example.com/simple

bar==4.5.6 ; {MARKER_PY} \\
    --hash=sha256:67890
foo==1.2.3 ; {MARKER_PY} \\
    --hash=sha256:12345
"""

    assert content == expected


def test_exporter_exports_requirements_txt_with_url_false(
    tmp_dir: str, poetry: Poetry
) -> None:
    poetry.pool.add_repository(
        LegacyRepository(
            "custom",
            "https://example.com/simple",
        )
    )
    poetry.locker.mock_lock_data(  # type: ignore[attr-defined]
        {
            "package": [
                {
                    "name": "foo",
                    "version": "1.2.3",
                    "category": "main",
                    "optional": False,
                    "python-versions": "*",
                },
                {
                    "name": "bar",
                    "version": "4.5.6",
                    "category": "dev",
                    "optional": False,
                    "python-versions": "*",
                    "source": {
                        "type": "legacy",
                        "url": "https://example.com/simple",
                        "reference": "",
                    },
                },
            ],
            "metadata": {
                "python-versions": "*",
                "content-hash": "123456789",
                "hashes": {"foo": ["12345"], "bar": ["67890"]},
            },
        }
    )
    set_package_requires(poetry)

    exporter = Exporter(poetry)
    exporter.only_groups([MAIN_GROUP, "dev"])
    exporter.with_urls(False)
    exporter.export("requirements.txt", Path(tmp_dir), "requirements.txt")

    with (Path(tmp_dir) / "requirements.txt").open(encoding="utf-8") as f:
        content = f.read()

    expected = f"""\
bar==4.5.6 ; {MARKER_PY} \\
    --hash=sha256:67890
foo==1.2.3 ; {MARKER_PY} \\
    --hash=sha256:12345
"""

    assert content == expected


def test_exporter_exports_requirements_txt_with_legacy_packages_trusted_host(
    tmp_dir: str, poetry: Poetry
) -> None:
    poetry.pool.add_repository(
        LegacyRepository(
            "custom",
            "http://example.com/simple",
        )
    )
    poetry.locker.mock_lock_data(  # type: ignore[attr-defined]
        {
            "package": [
                {
                    "name": "bar",
                    "version": "4.5.6",
                    "category": "dev",
                    "optional": False,
                    "python-versions": "*",
                    "source": {
                        "type": "legacy",
                        "url": "http://example.com/simple",
                        "reference": "",
                    },
                },
            ],
            "metadata": {
                "python-versions": "*",
                "content-hash": "123456789",
                "hashes": {"bar": ["67890"]},
            },
        }
    )
    set_package_requires(poetry)
    exporter = Exporter(poetry)
    exporter.only_groups([MAIN_GROUP, "dev"])
    exporter.export("requirements.txt", Path(tmp_dir), "requirements.txt")

    with (Path(tmp_dir) / "requirements.txt").open(encoding="utf-8") as f:
        content = f.read()

    expected = f"""\
--trusted-host example.com
--extra-index-url http://example.com/simple

bar==4.5.6 ; {MARKER_PY} \\
    --hash=sha256:67890
"""

    assert content == expected


@pytest.mark.parametrize(
    ["dev", "expected"],
    [
        (
            True,
            [
                f"bar==1.2.2 ; {MARKER_PY}",
                f"baz==1.2.3 ; {MARKER_PY}",
                f"foo==1.2.1 ; {MARKER_PY}",
            ],
        ),
        (
            False,
            [
                f"bar==1.2.2 ; {MARKER_PY}",
                f"foo==1.2.1 ; {MARKER_PY}",
            ],
        ),
    ],
)
def test_exporter_exports_requirements_txt_with_dev_extras(
    tmp_dir: str, poetry: Poetry, dev: bool, expected: list[str]
) -> None:
    poetry.locker.mock_lock_data(  # type: ignore[attr-defined]
        {
            "package": [
                {
                    "name": "foo",
                    "version": "1.2.1",
                    "category": "main",
                    "optional": False,
                    "python-versions": "*",
                },
                {
                    "name": "bar",
                    "version": "1.2.2",
                    "category": "main",
                    "optional": False,
                    "python-versions": "*",
                    "dependencies": {
                        "baz": {
                            "version": ">=0.1.0",
                            "optional": True,
                            "markers": "extra == 'baz'",
                        }
                    },
                    "extras": {"baz": ["baz (>=0.1.0)"]},
                },
                {
                    "name": "baz",
                    "version": "1.2.3",
                    "category": "dev",
                    "optional": False,
                    "python-versions": "*",
                },
            ],
            "metadata": {
                "python-versions": "*",
                "content-hash": "123456789",
                "hashes": {"foo": [], "bar": [], "baz": []},
            },
        }
    )
    set_package_requires(poetry)

    exporter = Exporter(poetry)
    if dev:
        exporter.only_groups([MAIN_GROUP, "dev"])
    exporter.export("requirements.txt", Path(tmp_dir), "requirements.txt")

    with (Path(tmp_dir) / "requirements.txt").open(encoding="utf-8") as f:
        content = f.read()

    assert content == "\n".join(expected) + "\n"


def test_exporter_exports_requirements_txt_with_legacy_packages_and_duplicate_sources(
    tmp_dir: str, poetry: Poetry
) -> None:
    poetry.pool.add_repository(
        LegacyRepository(
            "custom",
            "https://example.com/simple",
        )
    )
    poetry.pool.add_repository(
        LegacyRepository(
            "custom",
            "https://foobaz.com/simple",
        )
    )
    poetry.locker.mock_lock_data(  # type: ignore[attr-defined]
        {
            "package": [
                {
                    "name": "foo",
                    "version": "1.2.3",
                    "category": "main",
                    "optional": False,
                    "python-versions": "*",
                    "source": {
                        "type": "legacy",
                        "url": "https://example.com/simple",
                        "reference": "",
                    },
                },
                {
                    "name": "bar",
                    "version": "4.5.6",
                    "category": "dev",
                    "optional": False,
                    "python-versions": "*",
                    "source": {
                        "type": "legacy",
                        "url": "https://example.com/simple",
                        "reference": "",
                    },
                },
                {
                    "name": "baz",
                    "version": "7.8.9",
                    "category": "dev",
                    "optional": False,
                    "python-versions": "*",
                    "source": {
                        "type": "legacy",
                        "url": "https://foobaz.com/simple",
                        "reference": "",
                    },
                },
            ],
            "metadata": {
                "python-versions": "*",
                "content-hash": "123456789",
                "hashes": {"foo": ["12345"], "bar": ["67890"], "baz": ["24680"]},
            },
        }
    )
    set_package_requires(poetry)

    exporter = Exporter(poetry)
    exporter.only_groups([MAIN_GROUP, "dev"])
    exporter.export("requirements.txt", Path(tmp_dir), "requirements.txt")

    with (Path(tmp_dir) / "requirements.txt").open(encoding="utf-8") as f:
        content = f.read()

    expected = f"""\
--extra-index-url https://example.com/simple
--extra-index-url https://foobaz.com/simple

bar==4.5.6 ; {MARKER_PY} \\
    --hash=sha256:67890
baz==7.8.9 ; {MARKER_PY} \\
    --hash=sha256:24680
foo==1.2.3 ; {MARKER_PY} \\
    --hash=sha256:12345
"""

    assert content == expected


def test_exporter_exports_requirements_txt_with_legacy_packages_and_credentials(
    tmp_dir: str, poetry: Poetry, config: Config
) -> None:
    poetry.config.merge(
        {
            "repositories": {"custom": {"url": "https://example.com/simple"}},
            "http-basic": {"custom": {"username": "foo", "password": "bar"}},
        }
    )
    poetry.pool.add_repository(
        LegacyRepository("custom", "https://example.com/simple", config=poetry.config)
    )
    poetry.locker.mock_lock_data(  # type: ignore[attr-defined]
        {
            "package": [
                {
                    "name": "foo",
                    "version": "1.2.3",
                    "category": "main",
                    "optional": False,
                    "python-versions": "*",
                },
                {
                    "name": "bar",
                    "version": "4.5.6",
                    "category": "dev",
                    "optional": False,
                    "python-versions": "*",
                    "source": {
                        "type": "legacy",
                        "url": "https://example.com/simple",
                        "reference": "",
                    },
                },
            ],
            "metadata": {
                "python-versions": "*",
                "content-hash": "123456789",
                "hashes": {"foo": ["12345"], "bar": ["67890"]},
            },
        }
    )
    set_package_requires(poetry)

    exporter = Exporter(poetry)
    exporter.only_groups([MAIN_GROUP, "dev"])
    exporter.with_credentials()
    exporter.export(
        "requirements.txt",
        Path(tmp_dir),
        "requirements.txt",
    )

    with (Path(tmp_dir) / "requirements.txt").open(encoding="utf-8") as f:
        content = f.read()

    expected = f"""\
--extra-index-url https://foo:bar@example.com/simple

bar==4.5.6 ; {MARKER_PY} \\
    --hash=sha256:67890
foo==1.2.3 ; {MARKER_PY} \\
    --hash=sha256:12345
"""

    assert content == expected


def test_exporter_exports_requirements_txt_to_standard_output(
    tmp_dir: str, poetry: Poetry
) -> None:
    poetry.locker.mock_lock_data(  # type: ignore[attr-defined]
        {
            "package": [
                {
                    "name": "foo",
                    "version": "1.2.3",
                    "category": "main",
                    "optional": False,
                    "python-versions": "*",
                },
                {
                    "name": "bar",
                    "version": "4.5.6",
                    "category": "main",
                    "optional": False,
                    "python-versions": "*",
                },
            ],
            "metadata": {
                "python-versions": "*",
                "content-hash": "123456789",
                "hashes": {"foo": [], "bar": []},
            },
        }
    )
    set_package_requires(poetry)

    exporter = Exporter(poetry)
    io = BufferedIO()
    exporter.export("requirements.txt", Path(tmp_dir), io)

    expected = f"""\
bar==4.5.6 ; {MARKER_PY}
foo==1.2.3 ; {MARKER_PY}
"""

    assert io.fetch_output() == expected


def test_exporter_doesnt_confuse_repeated_packages(
    tmp_dir: str, poetry: Poetry
) -> None:
    # Testcase derived from <https://github.com/python-poetry/poetry/issues/5141>.
    poetry.locker.mock_lock_data(  # type: ignore[attr-defined]
        {
            "package": [
                {
                    "name": "celery",
                    "version": "5.1.2",
                    "category": "main",
                    "optional": False,
                    "python-versions": "<3.7",
                    "dependencies": {
                        "click": ">=7.0,<8.0",
                        "click-didyoumean": ">=0.0.3",
                        "click-plugins": ">=1.1.1",
                    },
                },
                {
                    "name": "celery",
                    "version": "5.2.3",
                    "category": "main",
                    "optional": False,
                    "python-versions": ">=3.7",
                    "dependencies": {
                        "click": ">=8.0.3,<9.0",
                        "click-didyoumean": ">=0.0.3",
                        "click-plugins": ">=1.1.1",
                    },
                },
                {
                    "name": "click",
                    "version": "7.1.2",
                    "category": "main",
                    "optional": False,
                    "python-versions": (
                        ">=2.7, !=3.0.*, !=3.1.*, !=3.2.*, !=3.3.*, !=3.4.*"
                    ),
                },
                {
                    "name": "click",
                    "version": "8.0.3",
                    "category": "main",
                    "optional": False,
                    "python-versions": ">=3.6",
                    "dependencies": {},
                },
                {
                    "name": "click-didyoumean",
                    "version": "0.0.3",
                    "category": "main",
                    "optional": False,
                    "python-versions": "*",
                    "dependencies": {"click": "*"},
                },
                {
                    "name": "click-didyoumean",
                    "version": "0.3.0",
                    "category": "main",
                    "optional": False,
                    "python-versions": ">=3.6.2,<4.0.0",
                    "dependencies": {"click": ">=7"},
                },
                {
                    "name": "click-plugins",
                    "version": "1.1.1",
                    "category": "main",
                    "optional": False,
                    "python-versions": "*",
                    "dependencies": {"click": ">=4.0"},
                },
            ],
            "metadata": {
                "lock-version": "1.1",
                "python-versions": "^3.6",
                "content-hash": (
                    "832b13a88e5020c27cbcd95faa577bf0dbf054a65c023b45dc9442b640d414e6"
                ),
                "hashes": {
                    "celery": [],
                    "click-didyoumean": [],
                    "click-plugins": [],
                    "click": [],
                },
            },
        }
    )
    root = poetry.package.with_dependency_groups([], only=True)
    root.python_versions = "^3.6"
    root.add_dependency(
        Factory.create_dependency(
            name="celery", constraint={"version": "5.1.2", "python": "<3.7"}
        )
    )
    root.add_dependency(
        Factory.create_dependency(
            name="celery", constraint={"version": "5.2.3", "python": ">=3.7"}
        )
    )
    poetry._package = root

    exporter = Exporter(poetry)
    exporter.only_groups([MAIN_GROUP, "dev"])
    io = BufferedIO()
    exporter.export("requirements.txt", Path(tmp_dir), io)

    expected = f"""\
celery==5.1.2 ; {MARKER_PY36_ONLY}
celery==5.2.3 ; {MARKER_PY37}
click-didyoumean==0.0.3 ; {MARKER_PY36_ONLY}
click-didyoumean==0.3.0 ; {MARKER_PY37_PY400}
click-plugins==1.1.1 ; {MARKER_PY36_ONLY.union(MARKER_PY37)}
click==7.1.2 ; {MARKER_PY36_ONLY}
click==8.0.3 ; {MARKER_PY37}
"""

    assert io.fetch_output() == expected


def test_exporter_handles_extras_next_to_non_extras(
    tmp_dir: str, poetry: Poetry
) -> None:
    # Testcase similar to the solver testcase added at #5305.
    poetry.locker.mock_lock_data(  # type: ignore[attr-defined]
        {
            "package": [
                {
                    "name": "localstack",
                    "python-versions": "*",
                    "version": "1.0.0",
                    "category": "main",
                    "optional": False,
                    "dependencies": {
                        "localstack-ext": [
                            {"version": ">=1.0.0"},
                            {
                                "version": ">=1.0.0",
                                "extras": ["bar"],
                                "markers": 'extra == "foo"',
                            },
                        ]
                    },
                    "extras": {"foo": ["localstack-ext (>=1.0.0)"]},
                },
                {
                    "name": "localstack-ext",
                    "python-versions": "*",
                    "version": "1.0.0",
                    "category": "main",
                    "optional": False,
                    "dependencies": {
                        "something": "*",
                        "something-else": {
                            "version": ">=1.0.0",
                            "markers": 'extra == "bar"',
                        },
                        "another-thing": {
                            "version": ">=1.0.0",
                            "markers": 'extra == "baz"',
                        },
                    },
                    "extras": {
                        "bar": ["something-else (>=1.0.0)"],
                        "baz": ["another-thing (>=1.0.0)"],
                    },
                },
                {
                    "name": "something",
                    "python-versions": "*",
                    "version": "1.0.0",
                    "category": "main",
                    "optional": False,
                    "dependencies": {},
                },
                {
                    "name": "something-else",
                    "python-versions": "*",
                    "version": "1.0.0",
                    "category": "main",
                    "optional": False,
                    "dependencies": {},
                },
                {
                    "name": "another-thing",
                    "python-versions": "*",
                    "version": "1.0.0",
                    "category": "main",
                    "optional": False,
                    "dependencies": {},
                },
            ],
            "metadata": {
                "lock-version": "1.1",
                "python-versions": "^3.6",
                "content-hash": (
                    "832b13a88e5020c27cbcd95faa577bf0dbf054a65c023b45dc9442b640d414e6"
                ),
                "hashes": {
                    "localstack": [],
                    "localstack-ext": [],
                    "something": [],
                    "something-else": [],
                    "another-thing": [],
                },
            },
        }
    )
    root = poetry.package.with_dependency_groups([], only=True)
    root.python_versions = "^3.6"
    root.add_dependency(
        Factory.create_dependency(
            name="localstack", constraint={"version": "^1.0.0", "extras": ["foo"]}
        )
    )
    poetry._package = root

    exporter = Exporter(poetry)
    io = BufferedIO()
    exporter.export("requirements.txt", Path(tmp_dir), io)

    expected = f"""\
localstack-ext==1.0.0 ; {MARKER_PY36}
localstack-ext[bar]==1.0.0 ; {MARKER_PY36}
localstack[foo]==1.0.0 ; {MARKER_PY36}
something-else==1.0.0 ; {MARKER_PY36}
something==1.0.0 ; {MARKER_PY36}
"""

    assert io.fetch_output() == expected
