from __future__ import annotations

from typing import TYPE_CHECKING
from typing import Any

import pytest

from cleo.io.buffered_io import BufferedIO
from cleo.io.null_io import NullIO
from poetry.core.constraints.version import Version
from poetry.core.packages.dependency import Dependency
from poetry.core.packages.dependency_group import MAIN_GROUP
from poetry.core.version.markers import parse_marker
from poetry.factory import Factory
from poetry.packages import Locker as BaseLocker
from poetry.repositories.legacy_repository import LegacyRepository
from poetry.repositories.repository_pool import Priority

from poetry_plugin_export.exporter import Exporter
from poetry_plugin_export.walker import DependencyWalkerError
from tests.markers import MARKER_CPYTHON
from tests.markers import MARKER_DARWIN
from tests.markers import MARKER_LINUX
from tests.markers import MARKER_PY
from tests.markers import MARKER_PY27
from tests.markers import MARKER_PY36
from tests.markers import MARKER_PY36_38
from tests.markers import MARKER_PY36_ONLY
from tests.markers import MARKER_PY36_PY362
from tests.markers import MARKER_PY37
from tests.markers import MARKER_PY362_PY40
from tests.markers import MARKER_PY_DARWIN
from tests.markers import MARKER_PY_LINUX
from tests.markers import MARKER_PY_WIN32
from tests.markers import MARKER_PY_WINDOWS
from tests.markers import MARKER_WIN32
from tests.markers import MARKER_WINDOWS


if TYPE_CHECKING:
    from collections.abc import Collection
    from pathlib import Path

    from packaging.utils import NormalizedName
    from poetry.poetry import Poetry

    from tests.conftest import Config


class Locker(BaseLocker):
    def __init__(self, fixture_root: Path) -> None:
        super().__init__(fixture_root / "poetry.lock", {})
        self._locked = True

    def locked(self, is_locked: bool = True) -> Locker:
        self._locked = is_locked

        return self

    def mock_lock_data(self, data: dict[str, Any]) -> None:
        self._lock_data = data

    def is_locked(self) -> bool:
        return self._locked

    def is_fresh(self) -> bool:
        return True

    def _get_content_hash(self) -> str:
        return "123456789"


@pytest.fixture
def locker(fixture_root: Path) -> Locker:
    return Locker(fixture_root)


@pytest.fixture
def poetry(fixture_root: Path, locker: Locker) -> Poetry:
    p = Factory().create_poetry(fixture_root / "sample_project")
    p._locker = locker

    return p


def set_package_requires(
    poetry: Poetry,
    skip: set[str] | None = None,
    dev: set[str] | None = None,
    markers: dict[str, str] | None = None,
) -> None:
    skip = skip or set()
    dev = dev or set()
    packages = poetry.locker.locked_repository().packages
    package = poetry.package.with_dependency_groups([], only=True)
    for pkg in packages:
        if pkg.name not in skip:
            dep = pkg.to_dependency()
            if pkg.name in dev:
                dep._groups = frozenset(["dev"])
            if markers and pkg.name in markers:
                dep._marker = parse_marker(markers[pkg.name])
            package.add_dependency(dep)

    poetry._package = package


def fix_lock_data(lock_data: dict[str, Any]) -> None:
    if Version.parse(lock_data["metadata"]["lock-version"]) >= Version.parse("2.1"):
        for locked_package in lock_data["package"]:
            locked_package["groups"] = ["main"]
            locked_package["files"] = lock_data["metadata"]["files"][
                locked_package["name"]
            ]
        del lock_data["metadata"]["files"]


@pytest.mark.parametrize("lock_version", ("1.1", "2.1"))
def test_exporter_can_export_requirements_txt_with_standard_packages(
    tmp_path: Path, poetry: Poetry, lock_version: str
) -> None:
    lock_data = {
        "package": [
            {
                "name": "foo",
                "version": "1.2.3",
                "optional": False,
                "python-versions": "*",
            },
            {
                "name": "bar",
                "version": "4.5.6",
                "optional": False,
                "python-versions": "*",
            },
        ],
        "metadata": {
            "lock-version": lock_version,
            "python-versions": "*",
            "content-hash": "123456789",
            "files": {"foo": [], "bar": []},
        },
    }
    fix_lock_data(lock_data)
    poetry.locker.mock_lock_data(lock_data)  # type: ignore[attr-defined]
    set_package_requires(poetry)

    exporter = Exporter(poetry, NullIO())
    exporter.export("requirements.txt", tmp_path, "requirements.txt")

    with (tmp_path / "requirements.txt").open(encoding="utf-8") as f:
        content = f.read()

    expected = f"""\
bar==4.5.6 ; {MARKER_PY}
foo==1.2.3 ; {MARKER_PY}
"""

    assert content == expected


@pytest.mark.parametrize("lock_version", ("1.1", "2.1"))
def test_exporter_can_export_requirements_txt_with_standard_packages_and_markers(
    tmp_path: Path, poetry: Poetry, lock_version: str
) -> None:
    lock_data: dict[str, Any] = {
        "package": [
            {
                "name": "foo",
                "version": "1.2.3",
                "optional": False,
                "python-versions": "*",
            },
            {
                "name": "bar",
                "version": "4.5.6",
                "optional": False,
                "python-versions": "*",
            },
            {
                "name": "baz",
                "version": "7.8.9",
                "optional": False,
                "python-versions": "*",
            },
        ],
        "metadata": {
            "lock-version": lock_version,
            "python-versions": "*",
            "content-hash": "123456789",
            "files": {"foo": [], "bar": [], "baz": []},
        },
    }
    fix_lock_data(lock_data)
    if lock_version == "2.1":
        lock_data["package"][0]["markers"] = "python_version < '3.7'"
        lock_data["package"][2]["markers"] = "sys_platform == 'win32'"
    poetry.locker.mock_lock_data(lock_data)  # type: ignore[attr-defined]
    markers = {
        "foo": "python_version < '3.7'",
        "bar": "extra =='foo'",
        "baz": "sys_platform == 'win32'",
    }
    set_package_requires(poetry, markers=markers)

    exporter = Exporter(poetry, NullIO())
    exporter.export("requirements.txt", tmp_path, "requirements.txt")

    with (tmp_path / "requirements.txt").open(encoding="utf-8") as f:
        content = f.read()

    expected = f"""\
bar==4.5.6 ; {MARKER_PY}
baz==7.8.9 ; {MARKER_PY_WIN32}
foo==1.2.3 ; {MARKER_PY27.union(MARKER_PY36_ONLY)}
"""

    assert content == expected


@pytest.mark.parametrize("lock_version", ("1.1", "2.1"))
def test_exporter_can_export_requirements_txt_poetry(
    tmp_path: Path, poetry: Poetry, lock_version: str
) -> None:
    """Regression test for #3254"""

    lock_data: dict[str, Any] = {
        "package": [
            {
                "name": "poetry",
                "version": "1.1.4",
                "optional": False,
                "python-versions": "*",
                "dependencies": {"keyring": "*"},
            },
            {
                "name": "junit-xml",
                "version": "1.9",
                "optional": False,
                "python-versions": "*",
                "dependencies": {"six": "*"},
            },
            {
                "name": "keyring",
                "version": "21.8.0",
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
                "optional": False,
                "python-versions": "*",
                "dependencies": {"cryptography": "*"},
            },
            {
                "name": "cryptography",
                "version": "3.2",
                "optional": False,
                "python-versions": "*",
                "dependencies": {"six": "*"},
            },
            {
                "name": "six",
                "version": "1.15.0",
                "optional": False,
                "python-versions": "*",
            },
        ],
        "metadata": {
            "lock-version": lock_version,
            "python-versions": "*",
            "content-hash": "123456789",
            "files": {
                "poetry": [],
                "keyring": [],
                "secretstorage": [],
                "cryptography": [],
                "six": [],
                "junit-xml": [],
            },
        },
    }
    fix_lock_data(lock_data)
    if lock_version == "2.1":
        lock_data["package"][3]["markers"] = "sys_platform == 'linux'"
        lock_data["package"][4]["markers"] = "sys_platform == 'linux'"
    poetry.locker.mock_lock_data(lock_data)  # type: ignore[attr-defined]
    set_package_requires(
        poetry, skip={"keyring", "secretstorage", "cryptography", "six"}
    )

    exporter = Exporter(poetry, NullIO())
    exporter.export("requirements.txt", tmp_path, "requirements.txt")

    with (tmp_path / "requirements.txt").open(encoding="utf-8") as f:
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


@pytest.mark.parametrize("lock_version", ("1.1", "2.1"))
def test_exporter_can_export_requirements_txt_pyinstaller(
    tmp_path: Path, poetry: Poetry, lock_version: str
) -> None:
    """Regression test for #3254"""

    lock_data: dict[str, Any] = {
        "package": [
            {
                "name": "pyinstaller",
                "version": "4.0",
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
                "optional": False,
                "python-versions": "*",
            },
            {
                "name": "macholib",
                "version": "1.8",
                "optional": False,
                "python-versions": "*",
                "dependencies": {"altgraph": ">=0.15"},
            },
        ],
        "metadata": {
            "lock-version": lock_version,
            "python-versions": "*",
            "content-hash": "123456789",
            "files": {"pyinstaller": [], "altgraph": [], "macholib": []},
        },
    }
    fix_lock_data(lock_data)
    if lock_version == "2.1":
        lock_data["package"][2]["markers"] = "sys_platform == 'darwin'"
    poetry.locker.mock_lock_data(lock_data)  # type: ignore[attr-defined]
    set_package_requires(poetry, skip={"altgraph", "macholib"})

    exporter = Exporter(poetry, NullIO())
    exporter.export("requirements.txt", tmp_path, "requirements.txt")

    with (tmp_path / "requirements.txt").open(encoding="utf-8") as f:
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


@pytest.mark.parametrize("lock_version", ("1.1", "2.1"))
def test_exporter_can_export_requirements_txt_with_nested_packages_and_markers(
    tmp_path: Path, poetry: Poetry, lock_version: str
) -> None:
    lock_data: dict[str, Any] = {
        "package": [
            {
                "name": "a",
                "version": "1.2.3",
                "optional": False,
                "python-versions": "*",
                "dependencies": {
                    "b": {
                        "version": ">=0.0.0",
                        "markers": "platform_system == 'Windows'",
                    },
                    "c": {
                        "version": ">=0.0.0",
                        "markers": "sys_platform == 'win32'",
                    },
                },
            },
            {
                "name": "b",
                "version": "4.5.6",
                "optional": False,
                "python-versions": "*",
                "dependencies": {"d": ">=0.0.0"},
            },
            {
                "name": "c",
                "version": "7.8.9",
                "optional": False,
                "python-versions": "*",
                "dependencies": {"d": ">=0.0.0"},
            },
            {
                "name": "d",
                "version": "0.0.1",
                "optional": False,
                "python-versions": "*",
            },
        ],
        "metadata": {
            "lock-version": lock_version,
            "python-versions": "*",
            "content-hash": "123456789",
            "files": {"a": [], "b": [], "c": [], "d": []},
        },
    }
    fix_lock_data(lock_data)
    if lock_version == "2.1":
        lock_data["package"][0]["markers"] = "python_version < '3.7'"
        lock_data["package"][1]["markers"] = (
            "python_version < '3.7' and platform_system == 'Windows'"
        )
        lock_data["package"][2]["markers"] = (
            "python_version < '3.7' and sys_platform == 'win32'"
        )
        lock_data["package"][3]["markers"] = (
            "python_version < '3.7' and platform_system == 'Windows'"
            " or python_version < '3.7' and sys_platform == 'win32'"
        )
    poetry.locker.mock_lock_data(lock_data)  # type: ignore[attr-defined]
    set_package_requires(
        poetry, skip={"b", "c", "d"}, markers={"a": "python_version < '3.7'"}
    )

    exporter = Exporter(poetry, NullIO())
    exporter.export("requirements.txt", tmp_path, "requirements.txt")

    with (tmp_path / "requirements.txt").open(encoding="utf-8") as f:
        content = f.read()

    marker_py = MARKER_PY27.union(MARKER_PY36_ONLY)
    marker_py_win32 = marker_py.intersect(MARKER_WIN32)
    marker_py_windows = marker_py.intersect(MARKER_WINDOWS)

    expected = {
        "a": Dependency.create_from_pep_508(f"a==1.2.3 ; {marker_py}"),
        "b": Dependency.create_from_pep_508(f"b==4.5.6 ; {marker_py_windows}"),
        "c": Dependency.create_from_pep_508(f"c==7.8.9 ; {marker_py_win32}"),
        "d": Dependency.create_from_pep_508(
            f"d==0.0.1 ; {marker_py_windows.union(marker_py_win32)}"
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
@pytest.mark.parametrize("lock_version", ("1.1", "2.1"))
def test_exporter_can_export_requirements_txt_with_nested_packages_and_markers_any(
    tmp_path: Path, poetry: Poetry, dev: bool, lines: list[str], lock_version: str
) -> None:
    lock_data: dict[str, Any] = {
        "package": [
            {
                "name": "a",
                "version": "1.2.3",
                "optional": False,
                "python-versions": "*",
            },
            {
                "name": "b",
                "version": "4.5.6",
                "optional": False,
                "python-versions": "*",
                "dependencies": {"a": ">=1.2.3"},
            },
        ],
        "metadata": {
            "lock-version": lock_version,
            "python-versions": "*",
            "content-hash": "123456789",
            "files": {"a": [], "b": []},
        },
    }
    fix_lock_data(lock_data)
    if lock_version == "2.1":
        lock_data["package"][0]["groups"] = ["main", "dev"]
        lock_data["package"][0]["markers"] = {"main": "python_version < '3.8'"}
        lock_data["package"][1]["groups"] = ["dev"]
    poetry.locker.mock_lock_data(lock_data)  # type: ignore[attr-defined]

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

    exporter = Exporter(poetry, NullIO())
    if dev:
        exporter.only_groups([MAIN_GROUP, "dev"])
    exporter.export("requirements.txt", tmp_path, "requirements.txt")

    with (tmp_path / "requirements.txt").open(encoding="utf-8") as f:
        content = f.read()

    assert content.strip() == "\n".join(lines)


@pytest.mark.parametrize("lock_version", ("1.1", "2.1"))
def test_exporter_can_export_requirements_txt_with_standard_packages_and_hashes(
    tmp_path: Path, poetry: Poetry, lock_version: str
) -> None:
    lock_data: dict[str, Any] = {
        "package": [
            {
                "name": "foo",
                "version": "1.2.3",
                "optional": False,
                "python-versions": "*",
            },
            {
                "name": "bar",
                "version": "4.5.6",
                "optional": False,
                "python-versions": "*",
            },
        ],
        "metadata": {
            "lock-version": lock_version,
            "python-versions": "*",
            "content-hash": "123456789",
            "files": {
                "foo": [{"name": "foo.whl", "hash": "12345"}],
                "bar": [{"name": "bar.whl", "hash": "67890"}],
            },
        },
    }
    fix_lock_data(lock_data)
    poetry.locker.mock_lock_data(lock_data)  # type: ignore[attr-defined]
    set_package_requires(poetry)

    exporter = Exporter(poetry, NullIO())
    exporter.export("requirements.txt", tmp_path, "requirements.txt")

    with (tmp_path / "requirements.txt").open(encoding="utf-8") as f:
        content = f.read()

    expected = f"""\
bar==4.5.6 ; {MARKER_PY} \\
    --hash=sha256:67890
foo==1.2.3 ; {MARKER_PY} \\
    --hash=sha256:12345
"""

    assert content == expected


@pytest.mark.parametrize("lock_version", ("1.1", "2.1"))
def test_exporter_can_export_requirements_txt_with_standard_packages_and_sorted_hashes(
    tmp_path: Path, poetry: Poetry, lock_version: str
) -> None:
    lock_data = {
        "package": [
            {
                "name": "foo",
                "version": "1.2.3",
                "optional": False,
                "python-versions": "*",
            },
            {
                "name": "bar",
                "version": "4.5.6",
                "optional": False,
                "python-versions": "*",
            },
        ],
        "metadata": {
            "lock-version": lock_version,
            "python-versions": "*",
            "content-hash": "123456789",
            "files": {
                "foo": [
                    {"name": "foo1.whl", "hash": "67890"},
                    {"name": "foo2.whl", "hash": "12345"},
                ],
                "bar": [
                    {"name": "bar1.whl", "hash": "67890"},
                    {"name": "bar2.whl", "hash": "12345"},
                ],
            },
        },
    }
    fix_lock_data(lock_data)
    poetry.locker.mock_lock_data(lock_data)  # type: ignore[attr-defined]
    set_package_requires(poetry)

    exporter = Exporter(poetry, NullIO())
    exporter.export("requirements.txt", tmp_path, "requirements.txt")

    with (tmp_path / "requirements.txt").open(encoding="utf-8") as f:
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


@pytest.mark.parametrize("lock_version", ("1.1", "2.1"))
def test_exporter_can_export_requirements_txt_with_standard_packages_and_hashes_disabled(
    tmp_path: Path, poetry: Poetry, lock_version: str
) -> None:
    lock_data = {
        "package": [
            {
                "name": "foo",
                "version": "1.2.3",
                "optional": False,
                "python-versions": "*",
            },
            {
                "name": "bar",
                "version": "4.5.6",
                "optional": False,
                "python-versions": "*",
            },
        ],
        "metadata": {
            "lock-version": lock_version,
            "python-versions": "*",
            "content-hash": "123456789",
            "files": {
                "foo": [{"name": "foo.whl", "hash": "12345"}],
                "bar": [{"name": "bar.whl", "hash": "67890"}],
            },
        },
    }
    fix_lock_data(lock_data)
    poetry.locker.mock_lock_data(lock_data)  # type: ignore[attr-defined]
    set_package_requires(poetry)

    exporter = Exporter(poetry, NullIO())
    exporter.with_hashes(False)
    exporter.export("requirements.txt", tmp_path, "requirements.txt")

    with (tmp_path / "requirements.txt").open(encoding="utf-8") as f:
        content = f.read()

    expected = f"""\
bar==4.5.6 ; {MARKER_PY}
foo==1.2.3 ; {MARKER_PY}
"""

    assert content == expected


@pytest.mark.parametrize("lock_version", ("1.1", "2.1"))
def test_exporter_exports_requirements_txt_without_dev_packages_by_default(
    tmp_path: Path, poetry: Poetry, lock_version: str
) -> None:
    lock_data: dict[str, Any] = {
        "package": [
            {
                "name": "foo",
                "version": "1.2.3",
                "optional": False,
                "python-versions": "*",
            },
            {
                "name": "bar",
                "version": "4.5.6",
                "optional": False,
                "python-versions": "*",
            },
        ],
        "metadata": {
            "lock-version": lock_version,
            "python-versions": "*",
            "content-hash": "123456789",
            "files": {
                "foo": [{"name": "foo.whl", "hash": "12345"}],
                "bar": [{"name": "bar.whl", "hash": "67890"}],
            },
        },
    }
    fix_lock_data(lock_data)
    if lock_version == "2.1":
        lock_data["package"][1]["groups"] = ["dev"]
    poetry.locker.mock_lock_data(lock_data)  # type: ignore[attr-defined]
    set_package_requires(poetry, dev={"bar"})

    exporter = Exporter(poetry, NullIO())
    exporter.export("requirements.txt", tmp_path, "requirements.txt")

    with (tmp_path / "requirements.txt").open(encoding="utf-8") as f:
        content = f.read()

    expected = f"""\
foo==1.2.3 ; {MARKER_PY} \\
    --hash=sha256:12345
"""

    assert content == expected


@pytest.mark.parametrize("lock_version", ("1.1", "2.1"))
def test_exporter_exports_requirements_txt_with_dev_packages_if_opted_in(
    tmp_path: Path, poetry: Poetry, lock_version: str
) -> None:
    lock_data: dict[str, Any] = {
        "package": [
            {
                "name": "foo",
                "version": "1.2.3",
                "optional": False,
                "python-versions": "*",
            },
            {
                "name": "bar",
                "version": "4.5.6",
                "optional": False,
                "python-versions": "*",
            },
        ],
        "metadata": {
            "lock-version": lock_version,
            "python-versions": "*",
            "content-hash": "123456789",
            "files": {
                "foo": [{"name": "foo.whl", "hash": "12345"}],
                "bar": [{"name": "bar.whl", "hash": "67890"}],
            },
        },
    }
    fix_lock_data(lock_data)
    if lock_version == "2.1":
        lock_data["package"][1]["groups"] = ["dev"]
    poetry.locker.mock_lock_data(lock_data)  # type: ignore[attr-defined]
    set_package_requires(poetry, dev={"bar"})

    exporter = Exporter(poetry, NullIO())
    exporter.only_groups([MAIN_GROUP, "dev"])
    exporter.export("requirements.txt", tmp_path, "requirements.txt")

    with (tmp_path / "requirements.txt").open(encoding="utf-8") as f:
        content = f.read()

    expected = f"""\
bar==4.5.6 ; {MARKER_PY} \\
    --hash=sha256:67890
foo==1.2.3 ; {MARKER_PY} \\
    --hash=sha256:12345
"""

    assert content == expected


@pytest.mark.parametrize("lock_version", ("1.1", "2.1"))
def test_exporter_exports_requirements_txt_without_groups_if_set_explicitly(
    tmp_path: Path, poetry: Poetry, lock_version: str
) -> None:
    lock_data: dict[str, Any] = {
        "package": [
            {
                "name": "foo",
                "version": "1.2.3",
                "optional": False,
                "python-versions": "*",
            },
            {
                "name": "bar",
                "version": "4.5.6",
                "optional": False,
                "python-versions": "*",
            },
        ],
        "metadata": {
            "lock-version": lock_version,
            "python-versions": "*",
            "content-hash": "123456789",
            "files": {
                "foo": [{"name": "foo.whl", "hash": "12345"}],
                "bar": [{"name": "bar.whl", "hash": "67890"}],
            },
        },
    }
    fix_lock_data(lock_data)
    if lock_version == "2.1":
        lock_data["package"][1]["groups"] = ["dev"]
    poetry.locker.mock_lock_data(lock_data)  # type: ignore[attr-defined]
    set_package_requires(poetry, dev={"bar"})

    exporter = Exporter(poetry, NullIO())
    exporter.only_groups([])
    exporter.export("requirements.txt", tmp_path, "requirements.txt")

    with (tmp_path / "requirements.txt").open(encoding="utf-8") as f:
        content = f.read()

    assert content == "\n"


@pytest.mark.parametrize("lock_version", ("1.1", "2.1"))
def test_exporter_exports_requirements_txt_without_optional_packages(
    tmp_path: Path, poetry: Poetry, lock_version: str
) -> None:
    lock_data: dict[str, Any] = {
        "package": [
            {
                "name": "foo",
                "version": "1.2.3",
                "optional": False,
                "python-versions": "*",
            },
            {
                "name": "bar",
                "version": "4.5.6",
                "optional": True,
                "python-versions": "*",
            },
        ],
        "metadata": {
            "lock-version": lock_version,
            "python-versions": "*",
            "content-hash": "123456789",
            "files": {
                "foo": [{"name": "foo.whl", "hash": "12345"}],
                "bar": [{"name": "bar.whl", "hash": "67890"}],
            },
        },
    }
    fix_lock_data(lock_data)
    if lock_version == "2.1":
        lock_data["package"][1]["groups"] = ["dev"]
        lock_data["package"][1]["markers"] = 'extra == "feature-bar"'
    poetry.locker.mock_lock_data(lock_data)  # type: ignore[attr-defined]
    set_package_requires(poetry, dev={"bar"})

    exporter = Exporter(poetry, NullIO())
    exporter.only_groups([MAIN_GROUP, "dev"])
    exporter.export("requirements.txt", tmp_path, "requirements.txt")

    with (tmp_path / "requirements.txt").open(encoding="utf-8") as f:
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
            ["feature-bar"],
            [
                f"bar==4.5.6 ; {MARKER_PY}",
                f"foo==1.2.3 ; {MARKER_PY}",
                f"spam==0.1.0 ; {MARKER_PY}",
            ],
        ),
    ],
)
@pytest.mark.parametrize("lock_version", ("1.1", "2.1"))
def test_exporter_exports_requirements_txt_with_optional_packages(
    tmp_path: Path,
    poetry: Poetry,
    extras: Collection[NormalizedName],
    lines: list[str],
    lock_version: str,
) -> None:
    lock_data: dict[str, Any] = {
        "package": [
            {
                "name": "foo",
                "version": "1.2.3",
                "optional": False,
                "python-versions": "*",
            },
            {
                "name": "bar",
                "version": "4.5.6",
                "optional": True,
                "python-versions": "*",
                "dependencies": {"spam": ">=0.1"},
            },
            {
                "name": "spam",
                "version": "0.1.0",
                "optional": True,
                "python-versions": "*",
            },
        ],
        "metadata": {
            "lock-version": lock_version,
            "python-versions": "*",
            "content-hash": "123456789",
            "files": {
                "foo": [{"name": "foo.whl", "hash": "12345"}],
                "bar": [{"name": "bar.whl", "hash": "67890"}],
                "spam": [{"name": "spam.whl", "hash": "abcde"}],
            },
        },
        "extras": {"feature_bar": ["bar"]},
    }
    fix_lock_data(lock_data)
    if lock_version == "2.1":
        lock_data["package"][1]["markers"] = 'extra == "feature-bar"'
        lock_data["package"][2]["markers"] = 'extra == "feature-bar"'
    poetry.locker.mock_lock_data(lock_data)  # type: ignore[attr-defined]
    set_package_requires(poetry)

    exporter = Exporter(poetry, NullIO())
    exporter.only_groups([MAIN_GROUP, "dev"])
    exporter.with_hashes(False)
    exporter.with_extras(extras)
    exporter.export(
        "requirements.txt",
        tmp_path,
        "requirements.txt",
    )

    with (tmp_path / "requirements.txt").open(encoding="utf-8") as f:
        content = f.read()

    expected = "\n".join(lines)

    assert content.strip() == expected


@pytest.mark.parametrize("lock_version", ("1.1", "2.1"))
def test_exporter_can_export_requirements_txt_with_git_packages(
    tmp_path: Path, poetry: Poetry, lock_version: str
) -> None:
    lock_data = {
        "package": [
            {
                "name": "foo",
                "version": "1.2.3",
                "optional": False,
                "python-versions": "*",
                "source": {
                    "type": "git",
                    "url": "https://github.com/foo/foo.git",
                    "reference": "123456",
                    "resolved_reference": "abcdef",
                },
            }
        ],
        "metadata": {
            "lock-version": lock_version,
            "python-versions": "*",
            "content-hash": "123456789",
            "files": {"foo": []},
        },
    }
    fix_lock_data(lock_data)
    poetry.locker.mock_lock_data(lock_data)  # type: ignore[attr-defined]
    set_package_requires(poetry)

    exporter = Exporter(poetry, NullIO())
    exporter.export("requirements.txt", tmp_path, "requirements.txt")

    with (tmp_path / "requirements.txt").open(encoding="utf-8") as f:
        content = f.read()

    expected = f"""\
foo @ git+https://github.com/foo/foo.git@abcdef ; {MARKER_PY}
"""

    assert content == expected


@pytest.mark.parametrize("lock_version", ("1.1", "2.1"))
def test_exporter_can_export_requirements_txt_with_nested_packages(
    tmp_path: Path, poetry: Poetry, lock_version: str
) -> None:
    lock_data = {
        "package": [
            {
                "name": "foo",
                "version": "1.2.3",
                "optional": False,
                "python-versions": "*",
                "source": {
                    "type": "git",
                    "url": "https://github.com/foo/foo.git",
                    "reference": "123456",
                    "resolved_reference": "abcdef",
                },
            },
            {
                "name": "bar",
                "version": "4.5.6",
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
            "lock-version": lock_version,
            "python-versions": "*",
            "content-hash": "123456789",
            "files": {"foo": [], "bar": []},
        },
    }
    fix_lock_data(lock_data)
    poetry.locker.mock_lock_data(lock_data)  # type: ignore[attr-defined]
    set_package_requires(poetry, skip={"foo"})

    exporter = Exporter(poetry, NullIO())
    exporter.export("requirements.txt", tmp_path, "requirements.txt")

    with (tmp_path / "requirements.txt").open(encoding="utf-8") as f:
        content = f.read()

    expected = f"""\
bar==4.5.6 ; {MARKER_PY}
foo @ git+https://github.com/foo/foo.git@abcdef ; {MARKER_PY}
"""

    assert content == expected


@pytest.mark.parametrize("lock_version", ("1.1", "2.1"))
def test_exporter_can_export_requirements_txt_with_nested_packages_cyclic(
    tmp_path: Path, poetry: Poetry, lock_version: str
) -> None:
    lock_data = {
        "package": [
            {
                "name": "foo",
                "version": "1.2.3",
                "optional": False,
                "python-versions": "*",
                "dependencies": {"bar": {"version": "4.5.6"}},
            },
            {
                "name": "bar",
                "version": "4.5.6",
                "optional": False,
                "python-versions": "*",
                "dependencies": {"baz": {"version": "7.8.9"}},
            },
            {
                "name": "baz",
                "version": "7.8.9",
                "optional": False,
                "python-versions": "*",
                "dependencies": {"foo": {"version": "1.2.3"}},
            },
        ],
        "metadata": {
            "lock-version": lock_version,
            "python-versions": "*",
            "content-hash": "123456789",
            "files": {"foo": [], "bar": [], "baz": []},
        },
    }
    fix_lock_data(lock_data)
    poetry.locker.mock_lock_data(lock_data)  # type: ignore[attr-defined]
    set_package_requires(poetry, skip={"bar", "baz"})

    exporter = Exporter(poetry, NullIO())
    exporter.export("requirements.txt", tmp_path, "requirements.txt")

    with (tmp_path / "requirements.txt").open(encoding="utf-8") as f:
        content = f.read()

    expected = f"""\
bar==4.5.6 ; {MARKER_PY}
baz==7.8.9 ; {MARKER_PY}
foo==1.2.3 ; {MARKER_PY}
"""

    assert content == expected


@pytest.mark.parametrize("lock_version", ("1.1", "2.1"))
def test_exporter_can_export_requirements_txt_with_circular_root_dependency(
    tmp_path: Path, poetry: Poetry, lock_version: str
) -> None:
    lock_data = {
        "package": [
            {
                "name": "foo",
                "version": "1.2.3",
                "optional": False,
                "python-versions": "*",
                "dependencies": {poetry.package.pretty_name: {"version": "1.2.3"}},
            },
        ],
        "metadata": {
            "lock-version": lock_version,
            "python-versions": "*",
            "content-hash": "123456789",
            "files": {"foo": []},
        },
    }
    fix_lock_data(lock_data)
    poetry.locker.mock_lock_data(lock_data)  # type: ignore[attr-defined]
    set_package_requires(poetry)

    exporter = Exporter(poetry, NullIO())
    exporter.export("requirements.txt", tmp_path, "requirements.txt")

    with (tmp_path / "requirements.txt").open(encoding="utf-8") as f:
        content = f.read()

    expected = f"""\
foo==1.2.3 ; {MARKER_PY}
"""

    assert content == expected


@pytest.mark.parametrize("lock_version", ("1.1", "2.1"))
def test_exporter_can_export_requirements_txt_with_nested_packages_and_multiple_markers(
    tmp_path: Path, poetry: Poetry, lock_version: str
) -> None:
    lock_data: dict[str, Any] = {
        "package": [
            {
                "name": "foo",
                "version": "1.2.3",
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
                "optional": True,
                "python-versions": "*",
            },
        ],
        "metadata": {
            "lock-version": lock_version,
            "python-versions": "*",
            "content-hash": "123456789",
            "files": {"foo": [], "bar": [], "baz": []},
        },
    }
    fix_lock_data(lock_data)
    if lock_version == "2.1":
        lock_data["package"][2]["markers"] = 'platform_system == "Windows"'
    poetry.locker.mock_lock_data(lock_data)  # type: ignore[attr-defined]
    set_package_requires(poetry)

    exporter = Exporter(poetry, NullIO())
    exporter.with_hashes(False)
    exporter.export("requirements.txt", tmp_path, "requirements.txt")

    with (tmp_path / "requirements.txt").open(encoding="utf-8") as f:
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


@pytest.mark.parametrize("lock_version", ("1.1", "2.1"))
def test_exporter_can_export_requirements_txt_with_git_packages_and_markers(
    tmp_path: Path, poetry: Poetry, lock_version: str
) -> None:
    lock_data: dict[str, Any] = {
        "package": [
            {
                "name": "foo",
                "version": "1.2.3",
                "optional": False,
                "python-versions": "*",
                "source": {
                    "type": "git",
                    "url": "https://github.com/foo/foo.git",
                    "reference": "123456",
                    "resolved_reference": "abcdef",
                },
            }
        ],
        "metadata": {
            "lock-version": lock_version,
            "python-versions": "*",
            "content-hash": "123456789",
            "files": {"foo": []},
        },
    }
    fix_lock_data(lock_data)
    if lock_version == "2.1":
        lock_data["package"][0]["markers"] = "python_version < '3.7'"
    poetry.locker.mock_lock_data(lock_data)  # type: ignore[attr-defined]
    set_package_requires(poetry, markers={"foo": "python_version < '3.7'"})

    exporter = Exporter(poetry, NullIO())
    exporter.export("requirements.txt", tmp_path, "requirements.txt")

    with (tmp_path / "requirements.txt").open(encoding="utf-8") as f:
        content = f.read()

    expected = f"""\
foo @ git+https://github.com/foo/foo.git@abcdef ; {MARKER_PY27.union(MARKER_PY36_ONLY)}
"""

    assert content == expected


@pytest.mark.parametrize("lock_version", ("1.1", "2.1"))
def test_exporter_can_export_requirements_txt_with_directory_packages(
    tmp_path: Path, poetry: Poetry, fixture_root_uri: str, lock_version: str
) -> None:
    lock_data = {
        "package": [
            {
                "name": "foo",
                "version": "1.2.3",
                "optional": False,
                "python-versions": "*",
                "source": {
                    "type": "directory",
                    "url": "sample_project",
                    "reference": "",
                },
            }
        ],
        "metadata": {
            "lock-version": lock_version,
            "python-versions": "*",
            "content-hash": "123456789",
            "files": {"foo": []},
        },
    }
    fix_lock_data(lock_data)
    poetry.locker.mock_lock_data(lock_data)  # type: ignore[attr-defined]
    set_package_requires(poetry)

    exporter = Exporter(poetry, NullIO())
    exporter.export("requirements.txt", tmp_path, "requirements.txt")

    with (tmp_path / "requirements.txt").open(encoding="utf-8") as f:
        content = f.read()

    expected = f"""\
foo @ {fixture_root_uri}/sample_project ; {MARKER_PY}
"""

    assert content == expected


@pytest.mark.parametrize("lock_version", ("1.1", "2.1"))
def test_exporter_can_export_requirements_txt_with_directory_packages_editable(
    tmp_path: Path, poetry: Poetry, fixture_root_uri: str, lock_version: str
) -> None:
    lock_data = {
        "package": [
            {
                "name": "foo",
                "version": "1.2.3",
                "optional": False,
                "python-versions": "*",
                "develop": True,
                "source": {
                    "type": "directory",
                    "url": "sample_project",
                    "reference": "",
                },
            }
        ],
        "metadata": {
            "lock-version": lock_version,
            "python-versions": "*",
            "content-hash": "123456789",
            "files": {"foo": []},
        },
    }
    fix_lock_data(lock_data)
    poetry.locker.mock_lock_data(lock_data)  # type: ignore[attr-defined]
    set_package_requires(poetry)

    exporter = Exporter(poetry, NullIO())
    exporter.export("requirements.txt", tmp_path, "requirements.txt")

    with (tmp_path / "requirements.txt").open(encoding="utf-8") as f:
        content = f.read()

    expected = f"""\
-e {fixture_root_uri}/sample_project ; {MARKER_PY}
"""

    assert content == expected


@pytest.mark.parametrize("lock_version", ("1.1", "2.1"))
def test_exporter_can_export_requirements_txt_with_nested_directory_packages(
    tmp_path: Path, poetry: Poetry, fixture_root_uri: str, lock_version: str
) -> None:
    lock_data = {
        "package": [
            {
                "name": "foo",
                "version": "1.2.3",
                "optional": False,
                "python-versions": "*",
                "source": {
                    "type": "directory",
                    "url": "sample_project",
                    "reference": "",
                },
            },
            {
                "name": "bar",
                "version": "4.5.6",
                "optional": False,
                "python-versions": "*",
                "source": {
                    "type": "directory",
                    "url": "sample_project/../project_with_nested_local/bar",
                    "reference": "",
                },
            },
            {
                "name": "baz",
                "version": "7.8.9",
                "optional": False,
                "python-versions": "*",
                "source": {
                    "type": "directory",
                    "url": "sample_project/../project_with_nested_local/bar/..",
                    "reference": "",
                },
            },
        ],
        "metadata": {
            "lock-version": lock_version,
            "python-versions": "*",
            "content-hash": "123456789",
            "files": {"foo": [], "bar": [], "baz": []},
        },
    }
    fix_lock_data(lock_data)
    poetry.locker.mock_lock_data(lock_data)  # type: ignore[attr-defined]
    set_package_requires(poetry)

    exporter = Exporter(poetry, NullIO())
    exporter.export("requirements.txt", tmp_path, "requirements.txt")

    with (tmp_path / "requirements.txt").open(encoding="utf-8") as f:
        content = f.read()

    expected = f"""\
bar @ {fixture_root_uri}/project_with_nested_local/bar ; {MARKER_PY}
baz @ {fixture_root_uri}/project_with_nested_local ; {MARKER_PY}
foo @ {fixture_root_uri}/sample_project ; {MARKER_PY}
"""

    assert content == expected


@pytest.mark.parametrize("lock_version", ("1.1", "2.1"))
def test_exporter_can_export_requirements_txt_with_directory_packages_and_markers(
    tmp_path: Path, poetry: Poetry, fixture_root_uri: str, lock_version: str
) -> None:
    lock_data: dict[str, Any] = {
        "package": [
            {
                "name": "foo",
                "version": "1.2.3",
                "optional": False,
                "python-versions": "*",
                "source": {
                    "type": "directory",
                    "url": "sample_project",
                    "reference": "",
                },
            }
        ],
        "metadata": {
            "lock-version": lock_version,
            "python-versions": "*",
            "content-hash": "123456789",
            "files": {"foo": []},
        },
    }
    fix_lock_data(lock_data)
    if lock_version == "2.1":
        lock_data["package"][0]["markers"] = "python_version < '3.7'"
    poetry.locker.mock_lock_data(lock_data)  # type: ignore[attr-defined]
    set_package_requires(poetry, markers={"foo": "python_version < '3.7'"})

    exporter = Exporter(poetry, NullIO())
    exporter.export("requirements.txt", tmp_path, "requirements.txt")

    with (tmp_path / "requirements.txt").open(encoding="utf-8") as f:
        content = f.read()

    expected = f"""\
foo @ {fixture_root_uri}/sample_project ;\
 {MARKER_PY27.union(MARKER_PY36_ONLY)}
"""

    assert content == expected


@pytest.mark.parametrize("lock_version", ("1.1", "2.1"))
def test_exporter_can_export_requirements_txt_with_file_packages(
    tmp_path: Path, poetry: Poetry, fixture_root_uri: str, lock_version: str
) -> None:
    lock_data = {
        "package": [
            {
                "name": "foo",
                "version": "1.2.3",
                "optional": False,
                "python-versions": "*",
                "source": {
                    "type": "file",
                    "url": "distributions/demo-0.1.0.tar.gz",
                    "reference": "",
                },
            }
        ],
        "metadata": {
            "lock-version": lock_version,
            "python-versions": "*",
            "content-hash": "123456789",
            "files": {"foo": []},
        },
    }
    fix_lock_data(lock_data)
    poetry.locker.mock_lock_data(lock_data)  # type: ignore[attr-defined]
    set_package_requires(poetry)

    exporter = Exporter(poetry, NullIO())
    exporter.export("requirements.txt", tmp_path, "requirements.txt")

    with (tmp_path / "requirements.txt").open(encoding="utf-8") as f:
        content = f.read()

    expected = f"""\
foo @ {fixture_root_uri}/distributions/demo-0.1.0.tar.gz ;\
 {MARKER_PY}
"""

    assert content == expected


@pytest.mark.parametrize("lock_version", ("1.1", "2.1"))
def test_exporter_can_export_requirements_txt_with_file_packages_and_markers(
    tmp_path: Path, poetry: Poetry, fixture_root_uri: str, lock_version: str
) -> None:
    lock_data: dict[str, Any] = {
        "package": [
            {
                "name": "foo",
                "version": "1.2.3",
                "optional": False,
                "python-versions": "*",
                "source": {
                    "type": "file",
                    "url": "distributions/demo-0.1.0.tar.gz",
                    "reference": "",
                },
            }
        ],
        "metadata": {
            "lock-version": lock_version,
            "python-versions": "*",
            "content-hash": "123456789",
            "files": {"foo": []},
        },
    }
    fix_lock_data(lock_data)
    if lock_version == "2.1":
        lock_data["package"][0]["markers"] = "python_version < '3.7'"
    poetry.locker.mock_lock_data(lock_data)  # type: ignore[attr-defined]
    set_package_requires(poetry, markers={"foo": "python_version < '3.7'"})

    exporter = Exporter(poetry, NullIO())
    exporter.export("requirements.txt", tmp_path, "requirements.txt")

    with (tmp_path / "requirements.txt").open(encoding="utf-8") as f:
        content = f.read()

    uri = f"{fixture_root_uri}/distributions/demo-0.1.0.tar.gz"
    expected = f"""\
foo @ {uri} ; {MARKER_PY27.union(MARKER_PY36_ONLY)}
"""

    assert content == expected


@pytest.mark.parametrize("lock_version", ("1.1", "2.1"))
def test_exporter_exports_requirements_txt_with_legacy_packages(
    tmp_path: Path, poetry: Poetry, lock_version: str
) -> None:
    poetry.pool.add_repository(
        LegacyRepository(
            "custom",
            "https://example.com/simple",
        )
    )
    lock_data: dict[str, Any] = {
        "package": [
            {
                "name": "foo",
                "version": "1.2.3",
                "optional": False,
                "python-versions": "*",
            },
            {
                "name": "bar",
                "version": "4.5.6",
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
            "lock-version": lock_version,
            "python-versions": "*",
            "content-hash": "123456789",
            "files": {
                "foo": [{"name": "foo.whl", "hash": "12345"}],
                "bar": [{"name": "bar.whl", "hash": "67890"}],
            },
        },
    }
    fix_lock_data(lock_data)
    if lock_version == "2.1":
        lock_data["package"][1]["groups"] = ["dev"]
    poetry.locker.mock_lock_data(lock_data)  # type: ignore[attr-defined]
    set_package_requires(poetry, dev={"bar"})

    exporter = Exporter(poetry, NullIO())
    exporter.only_groups([MAIN_GROUP, "dev"])
    exporter.export("requirements.txt", tmp_path, "requirements.txt")

    with (tmp_path / "requirements.txt").open(encoding="utf-8") as f:
        content = f.read()

    expected = f"""\
--extra-index-url https://example.com/simple

bar==4.5.6 ; {MARKER_PY} \\
    --hash=sha256:67890
foo==1.2.3 ; {MARKER_PY} \\
    --hash=sha256:12345
"""

    assert content == expected


@pytest.mark.parametrize("lock_version", ("1.1", "2.1"))
def test_exporter_exports_requirements_txt_with_url_false(
    tmp_path: Path, poetry: Poetry, lock_version: str
) -> None:
    poetry.pool.add_repository(
        LegacyRepository(
            "custom",
            "https://example.com/simple",
        )
    )
    lock_data: dict[str, Any] = {
        "package": [
            {
                "name": "foo",
                "version": "1.2.3",
                "optional": False,
                "python-versions": "*",
            },
            {
                "name": "bar",
                "version": "4.5.6",
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
            "lock-version": lock_version,
            "python-versions": "*",
            "content-hash": "123456789",
            "files": {
                "foo": [{"name": "foo.whl", "hash": "12345"}],
                "bar": [{"name": "bar.whl", "hash": "67890"}],
            },
        },
    }
    fix_lock_data(lock_data)
    if lock_version == "2.1":
        lock_data["package"][1]["groups"] = ["dev"]
    poetry.locker.mock_lock_data(lock_data)  # type: ignore[attr-defined]
    set_package_requires(poetry, dev={"bar"})

    exporter = Exporter(poetry, NullIO())
    exporter.only_groups([MAIN_GROUP, "dev"])
    exporter.with_urls(False)
    exporter.export("requirements.txt", tmp_path, "requirements.txt")

    with (tmp_path / "requirements.txt").open(encoding="utf-8") as f:
        content = f.read()

    expected = f"""\
bar==4.5.6 ; {MARKER_PY} \\
    --hash=sha256:67890
foo==1.2.3 ; {MARKER_PY} \\
    --hash=sha256:12345
"""

    assert content == expected


@pytest.mark.parametrize("lock_version", ("1.1", "2.1"))
def test_exporter_exports_requirements_txt_with_legacy_packages_trusted_host(
    tmp_path: Path, poetry: Poetry, lock_version: str
) -> None:
    poetry.pool.add_repository(
        LegacyRepository(
            "custom",
            "http://example.com/simple",
        )
    )
    lock_data: dict[str, Any] = {
        "package": [
            {
                "name": "bar",
                "version": "4.5.6",
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
            "lock-version": lock_version,
            "python-versions": "*",
            "content-hash": "123456789",
            "files": {
                "bar": [{"name": "bar.whl", "hash": "67890"}],
            },
        },
    }
    fix_lock_data(lock_data)
    if lock_version == "2.1":
        lock_data["package"][0]["groups"] = ["dev"]
    poetry.locker.mock_lock_data(lock_data)  # type: ignore[attr-defined]
    set_package_requires(poetry, dev={"bar"})
    exporter = Exporter(poetry, NullIO())
    exporter.only_groups([MAIN_GROUP, "dev"])
    exporter.export("requirements.txt", tmp_path, "requirements.txt")

    with (tmp_path / "requirements.txt").open(encoding="utf-8") as f:
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
@pytest.mark.parametrize("lock_version", ("1.1", "2.1"))
def test_exporter_exports_requirements_txt_with_dev_extras(
    tmp_path: Path, poetry: Poetry, dev: bool, expected: list[str], lock_version: str
) -> None:
    lock_data: dict[str, Any] = {
        "package": [
            {
                "name": "foo",
                "version": "1.2.1",
                "optional": False,
                "python-versions": "*",
            },
            {
                "name": "bar",
                "version": "1.2.2",
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
                "optional": False,
                "python-versions": "*",
            },
        ],
        "metadata": {
            "lock-version": lock_version,
            "python-versions": "*",
            "content-hash": "123456789",
            "files": {"foo": [], "bar": [], "baz": []},
        },
    }
    fix_lock_data(lock_data)
    if lock_version == "2.1":
        lock_data["package"][2]["groups"] = ["dev"]
    poetry.locker.mock_lock_data(lock_data)  # type: ignore[attr-defined]
    set_package_requires(poetry, dev={"baz"})

    exporter = Exporter(poetry, NullIO())
    if dev:
        exporter.only_groups([MAIN_GROUP, "dev"])
    exporter.export("requirements.txt", tmp_path, "requirements.txt")

    with (tmp_path / "requirements.txt").open(encoding="utf-8") as f:
        content = f.read()

    assert content == "\n".join(expected) + "\n"


@pytest.mark.parametrize("lock_version", ("1.1", "2.1"))
def test_exporter_exports_requirements_txt_with_legacy_packages_and_duplicate_sources(
    tmp_path: Path, poetry: Poetry, lock_version: str
) -> None:
    poetry.pool.add_repository(
        LegacyRepository(
            "custom-example",
            "https://example.com/simple",
        )
    )
    poetry.pool.add_repository(
        LegacyRepository(
            "custom-foobaz",
            "https://foobaz.com/simple",
        )
    )
    lock_data: dict[str, Any] = {
        "package": [
            {
                "name": "foo",
                "version": "1.2.3",
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
            "lock-version": lock_version,
            "python-versions": "*",
            "content-hash": "123456789",
            "files": {
                "foo": [{"name": "foo.whl", "hash": "12345"}],
                "bar": [{"name": "bar.whl", "hash": "67890"}],
                "baz": [{"name": "baz.whl", "hash": "24680"}],
            },
        },
    }
    fix_lock_data(lock_data)
    if lock_version == "2.1":
        lock_data["package"][1]["groups"] = ["dev"]
        lock_data["package"][2]["groups"] = ["dev"]
    poetry.locker.mock_lock_data(lock_data)  # type: ignore[attr-defined]
    set_package_requires(poetry, dev={"bar", "baz"})

    exporter = Exporter(poetry, NullIO())
    exporter.only_groups([MAIN_GROUP, "dev"])
    exporter.export("requirements.txt", tmp_path, "requirements.txt")

    with (tmp_path / "requirements.txt").open(encoding="utf-8") as f:
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


@pytest.mark.parametrize("lock_version", ("1.1", "2.1"))
def test_exporter_exports_requirements_txt_with_two_primary_sources(
    tmp_path: Path, poetry: Poetry, lock_version: str
) -> None:
    poetry.pool.remove_repository("PyPI")
    poetry.config.merge(
        {
            "repositories": {
                "custom-a": {"url": "https://a.example.com/simple"},
                "custom-b": {"url": "https://b.example.com/simple"},
            },
            "http-basic": {
                "custom-a": {"username": "foo", "password": "bar"},
                "custom-b": {"username": "baz", "password": "qux"},
            },
        }
    )
    poetry.pool.add_repository(
        LegacyRepository(
            "custom-b",
            "https://b.example.com/simple",
            config=poetry.config,
        ),
    )
    poetry.pool.add_repository(
        LegacyRepository(
            "custom-a",
            "https://a.example.com/simple",
            config=poetry.config,
        ),
    )
    lock_data: dict[str, Any] = {
        "package": [
            {
                "name": "foo",
                "version": "1.2.3",
                "optional": False,
                "python-versions": "*",
                "source": {
                    "type": "legacy",
                    "url": "https://a.example.com/simple",
                    "reference": "",
                },
            },
            {
                "name": "bar",
                "version": "4.5.6",
                "optional": False,
                "python-versions": "*",
                "source": {
                    "type": "legacy",
                    "url": "https://b.example.com/simple",
                    "reference": "",
                },
            },
            {
                "name": "baz",
                "version": "7.8.9",
                "optional": False,
                "python-versions": "*",
                "source": {
                    "type": "legacy",
                    "url": "https://b.example.com/simple",
                    "reference": "",
                },
            },
        ],
        "metadata": {
            "lock-version": lock_version,
            "python-versions": "*",
            "content-hash": "123456789",
            "files": {
                "foo": [{"name": "foo.whl", "hash": "12345"}],
                "bar": [{"name": "bar.whl", "hash": "67890"}],
                "baz": [{"name": "baz.whl", "hash": "24680"}],
            },
        },
    }
    fix_lock_data(lock_data)
    if lock_version == "2.1":
        lock_data["package"][1]["groups"] = ["dev"]
        lock_data["package"][2]["groups"] = ["dev"]
    poetry.locker.mock_lock_data(lock_data)  # type: ignore[attr-defined]
    set_package_requires(poetry, dev={"bar", "baz"})

    exporter = Exporter(poetry, NullIO())
    exporter.only_groups([MAIN_GROUP, "dev"])
    exporter.with_credentials()
    exporter.export("requirements.txt", tmp_path, "requirements.txt")

    with (tmp_path / "requirements.txt").open(encoding="utf-8") as f:
        content = f.read()

    expected = f"""\
--index-url https://baz:qux@b.example.com/simple
--extra-index-url https://foo:bar@a.example.com/simple

bar==4.5.6 ; {MARKER_PY} \\
    --hash=sha256:67890
baz==7.8.9 ; {MARKER_PY} \\
    --hash=sha256:24680
foo==1.2.3 ; {MARKER_PY} \\
    --hash=sha256:12345
"""

    assert content == expected


@pytest.mark.parametrize("lock_version", ("1.1", "2.1"))
def test_exporter_exports_requirements_txt_with_legacy_packages_and_credentials(
    tmp_path: Path, poetry: Poetry, config: Config, lock_version: str
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
    lock_data: dict[str, Any] = {
        "package": [
            {
                "name": "foo",
                "version": "1.2.3",
                "optional": False,
                "python-versions": "*",
            },
            {
                "name": "bar",
                "version": "4.5.6",
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
            "lock-version": lock_version,
            "python-versions": "*",
            "content-hash": "123456789",
            "files": {
                "foo": [{"name": "foo.whl", "hash": "12345"}],
                "bar": [{"name": "bar.whl", "hash": "67890"}],
            },
        },
    }
    fix_lock_data(lock_data)
    if lock_version == "2.1":
        lock_data["package"][1]["groups"] = ["dev"]
    poetry.locker.mock_lock_data(lock_data)  # type: ignore[attr-defined]
    set_package_requires(poetry, dev={"bar"})

    exporter = Exporter(poetry, NullIO())
    exporter.only_groups([MAIN_GROUP, "dev"])
    exporter.with_credentials()
    exporter.export(
        "requirements.txt",
        tmp_path,
        "requirements.txt",
    )

    with (tmp_path / "requirements.txt").open(encoding="utf-8") as f:
        content = f.read()

    expected = f"""\
--extra-index-url https://foo:bar@example.com/simple

bar==4.5.6 ; {MARKER_PY} \\
    --hash=sha256:67890
foo==1.2.3 ; {MARKER_PY} \\
    --hash=sha256:12345
"""

    assert content == expected


@pytest.mark.parametrize("lock_version", ("1.1", "2.1"))
def test_exporter_exports_requirements_txt_to_standard_output(
    tmp_path: Path, poetry: Poetry, lock_version: str
) -> None:
    lock_data = {
        "package": [
            {
                "name": "foo",
                "version": "1.2.3",
                "optional": False,
                "python-versions": "*",
            },
            {
                "name": "bar",
                "version": "4.5.6",
                "optional": False,
                "python-versions": "*",
            },
        ],
        "metadata": {
            "lock-version": lock_version,
            "python-versions": "*",
            "content-hash": "123456789",
            "files": {"foo": [], "bar": []},
        },
    }
    fix_lock_data(lock_data)
    poetry.locker.mock_lock_data(lock_data)  # type: ignore[attr-defined]
    set_package_requires(poetry)

    exporter = Exporter(poetry, NullIO())
    io = BufferedIO()
    exporter.export("requirements.txt", tmp_path, io)

    expected = f"""\
bar==4.5.6 ; {MARKER_PY}
foo==1.2.3 ; {MARKER_PY}
"""

    assert io.fetch_output() == expected


@pytest.mark.parametrize("lock_version", ("1.1", "2.1"))
def test_exporter_doesnt_confuse_repeated_packages(
    tmp_path: Path, poetry: Poetry, lock_version: str
) -> None:
    # Testcase derived from <https://github.com/python-poetry/poetry/issues/5141>.
    lock_data: dict[str, Any] = {
        "package": [
            {
                "name": "celery",
                "version": "5.1.2",
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
                "optional": False,
                "python-versions": ">=2.7, !=3.0.*, !=3.1.*, !=3.2.*, !=3.3.*, !=3.4.*",
            },
            {
                "name": "click",
                "version": "8.0.3",
                "optional": False,
                "python-versions": ">=3.6",
                "dependencies": {},
            },
            {
                "name": "click-didyoumean",
                "version": "0.0.3",
                "optional": False,
                "python-versions": "*",
                "dependencies": {"click": "*"},
            },
            {
                "name": "click-didyoumean",
                "version": "0.3.0",
                "optional": False,
                "python-versions": ">=3.6.2,<4.0.0",
                "dependencies": {"click": ">=7"},
            },
            {
                "name": "click-plugins",
                "version": "1.1.1",
                "optional": False,
                "python-versions": "*",
                "dependencies": {"click": ">=4.0"},
            },
        ],
        "metadata": {
            "lock-version": lock_version,
            "python-versions": "^3.6",
            "content-hash": (
                "832b13a88e5020c27cbcd95faa577bf0dbf054a65c023b45dc9442b640d414e6"
            ),
            "files": {
                "celery": [],
                "click-didyoumean": [],
                "click-plugins": [],
                "click": [],
            },
        },
    }
    fix_lock_data(lock_data)
    if lock_version == "2.1":
        lock_data["package"][0]["markers"] = "python_version < '3.7'"
        lock_data["package"][1]["markers"] = "python_version >= '3.7'"
        lock_data["package"][2]["markers"] = "python_version < '3.7'"
        lock_data["package"][3]["markers"] = "python_version >= '3.7'"
        lock_data["package"][4]["markers"] = "python_full_version < '3.6.2'"
        lock_data["package"][5]["markers"] = "python_full_version >= '3.6.2'"
    poetry.locker.mock_lock_data(lock_data)  # type: ignore[attr-defined]
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

    exporter = Exporter(poetry, NullIO())
    exporter.only_groups([MAIN_GROUP, "dev"])
    io = BufferedIO()
    exporter.export("requirements.txt", tmp_path, io)

    expected = f"""\
celery==5.1.2 ; {MARKER_PY36_ONLY}
celery==5.2.3 ; {MARKER_PY37}
click-didyoumean==0.0.3 ; {MARKER_PY36_PY362}
click-didyoumean==0.3.0 ; {MARKER_PY362_PY40}
click-plugins==1.1.1 ; {MARKER_PY36}
click==7.1.2 ; {MARKER_PY36_ONLY}
click==8.0.3 ; {MARKER_PY37}
"""

    assert io.fetch_output() == expected


@pytest.mark.parametrize("lock_version", ("1.1", "2.1"))
def test_exporter_handles_extras_next_to_non_extras(
    tmp_path: Path, poetry: Poetry, lock_version: str
) -> None:
    # Testcase similar to the solver testcase added at #5305.
    lock_data = {
        "package": [
            {
                "name": "localstack",
                "python-versions": "*",
                "version": "1.0.0",
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
                "extras": {"foo": ["localstack-ext[bar] (>=1.0.0)"]},
            },
            {
                "name": "localstack-ext",
                "python-versions": "*",
                "version": "1.0.0",
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
                "optional": False,
                "dependencies": {},
            },
            {
                "name": "something-else",
                "python-versions": "*",
                "version": "1.0.0",
                "optional": False,
                "dependencies": {},
            },
        ],
        "metadata": {
            "lock-version": lock_version,
            "python-versions": "^3.6",
            "content-hash": (
                "832b13a88e5020c27cbcd95faa577bf0dbf054a65c023b45dc9442b640d414e6"
            ),
            "files": {
                "localstack": [],
                "localstack-ext": [],
                "something": [],
                "something-else": [],
                "another-thing": [],
            },
        },
    }
    fix_lock_data(lock_data)
    poetry.locker.mock_lock_data(lock_data)  # type: ignore[attr-defined]
    root = poetry.package.with_dependency_groups([], only=True)
    root.python_versions = "^3.6"
    root.add_dependency(
        Factory.create_dependency(
            name="localstack", constraint={"version": "^1.0.0", "extras": ["foo"]}
        )
    )
    poetry._package = root

    exporter = Exporter(poetry, NullIO())
    io = BufferedIO()
    exporter.export("requirements.txt", tmp_path, io)

    # It does not matter whether packages are exported with extras or not
    # because all dependencies are listed explicitly.
    if lock_version == "1.1":
        expected = f"""\
localstack-ext==1.0.0 ; {MARKER_PY36}
localstack-ext[bar]==1.0.0 ; {MARKER_PY36}
localstack[foo]==1.0.0 ; {MARKER_PY36}
something-else==1.0.0 ; {MARKER_PY36}
something==1.0.0 ; {MARKER_PY36}
"""
    else:
        expected = f"""\
localstack-ext==1.0.0 ; {MARKER_PY36}
localstack==1.0.0 ; {MARKER_PY36}
something-else==1.0.0 ; {MARKER_PY36}
something==1.0.0 ; {MARKER_PY36}
"""

    assert io.fetch_output() == expected


@pytest.mark.parametrize("lock_version", ("1.1", "2.1"))
def test_exporter_handles_overlapping_python_versions(
    tmp_path: Path, poetry: Poetry, lock_version: str
) -> None:
    # Testcase derived from
    # https://github.com/python-poetry/poetry-plugin-export/issues/32.
    lock_data: dict[str, Any] = {
        "package": [
            {
                "name": "ipython",
                "python-versions": ">=3.6",
                "version": "7.16.3",
                "optional": False,
                "dependencies": {},
            },
            {
                "name": "ipython",
                "python-versions": ">=3.7",
                "version": "7.34.0",
                "optional": False,
                "dependencies": {},
            },
            {
                "name": "slash",
                "python-versions": ">=3.6.*",
                "version": "1.13.0",
                "optional": False,
                "dependencies": {
                    "ipython": [
                        {
                            "version": "*",
                            "markers": (
                                'python_version >= "3.6" and implementation_name !='
                                ' "pypy"'
                            ),
                        },
                        {
                            "version": "<7.17.0",
                            "markers": (
                                'python_version < "3.6" and implementation_name !='
                                ' "pypy"'
                            ),
                        },
                    ],
                },
            },
        ],
        "metadata": {
            "lock-version": lock_version,
            "python-versions": "^3.6",
            "content-hash": (
                "832b13a88e5020c27cbcd95faa577bf0dbf054a65c023b45dc9442b640d414e6"
            ),
            "files": {
                "ipython": [],
                "slash": [],
            },
        },
    }
    fix_lock_data(lock_data)
    if lock_version == "2.1":
        lock_data["package"][0]["markers"] = (
            "python_version >= '3.6' and python_version < '3.7'"
        )
        lock_data["package"][1]["markers"] = "python_version >= '3.7'"
        lock_data["package"][2]["markers"] = "implementation_name == 'cpython'"
    poetry.locker.mock_lock_data(lock_data)  # type: ignore[attr-defined]
    root = poetry.package.with_dependency_groups([], only=True)
    root.python_versions = "^3.6"
    root.add_dependency(
        Factory.create_dependency(
            name="ipython",
            constraint={"version": "*", "python": "~3.6"},
        )
    )
    root.add_dependency(
        Factory.create_dependency(
            name="ipython",
            constraint={"version": "^7.17", "python": "^3.7"},
        )
    )
    root.add_dependency(
        Factory.create_dependency(
            name="slash",
            constraint={
                "version": "^1.12",
                "markers": "implementation_name == 'cpython'",
            },
        )
    )
    poetry._package = root

    exporter = Exporter(poetry, NullIO())
    io = BufferedIO()
    exporter.export("requirements.txt", tmp_path, io)

    expected = f"""\
ipython==7.16.3 ; {MARKER_PY36_ONLY}
ipython==7.34.0 ; {MARKER_PY37}
slash==1.13.0 ; {MARKER_PY36} and {MARKER_CPYTHON}
"""

    assert io.fetch_output() == expected


@pytest.mark.parametrize(
    ["with_extras", "expected"],
    [
        (
            True,
            [f"foo[test]==1.0.0 ; {MARKER_PY36}", f"pytest==6.24.0 ; {MARKER_PY36}"],
        ),
        (
            False,
            [f"foo==1.0.0 ; {MARKER_PY36}"],
        ),
    ],
)
@pytest.mark.parametrize("lock_version", ("1.1", "2.1"))
def test_exporter_omits_unwanted_extras(
    tmp_path: Path,
    poetry: Poetry,
    with_extras: bool,
    expected: list[str],
    lock_version: str,
) -> None:
    # Testcase derived from
    # https://github.com/python-poetry/poetry/issues/5779
    lock_data: dict[str, Any] = {
        "package": [
            {
                "name": "foo",
                "python-versions": ">=3.6",
                "version": "1.0.0",
                "optional": False,
                "dependencies": {"pytest": {"version": "^6.2.4", "optional": True}},
                "extras": {"test": ["pytest (>=6.2.4,<7.0.0)"]},
            },
            {
                "name": "pytest",
                "python-versions": ">=3.6",
                "version": "6.24.0",
                "optional": False,
                "dependencies": {},
            },
        ],
        "metadata": {
            "lock-version": lock_version,
            "python-versions": "^3.6",
            "content-hash": (
                "832b13a88e5020c27cbcd95faa577bf0dbf054a65c023b45dc9442b640d414e6"
            ),
            "files": {
                "foo": [],
                "pytest": [],
            },
        },
    }
    fix_lock_data(lock_data)
    if lock_version == "2.1":
        lock_data["package"][0]["groups"] = ["main", "with-extras"]
        lock_data["package"][1]["groups"] = ["with-extras"]
    poetry.locker.mock_lock_data(lock_data)  # type: ignore[attr-defined]
    root = poetry.package.with_dependency_groups([], only=True)
    root.python_versions = "^3.6"
    root.add_dependency(
        Factory.create_dependency(
            name="foo",
            constraint={"version": "*"},
        )
    )
    root.add_dependency(
        Factory.create_dependency(
            name="foo",
            constraint={"version": "*", "extras": ["test"]},
            groups=["with-extras"],
        )
    )
    poetry._package = root

    io = BufferedIO()
    exporter = Exporter(poetry, NullIO())
    if with_extras:
        exporter.only_groups(["with-extras"])
        # It does not matter whether packages are exported with extras or not
        # because all dependencies are listed explicitly.
        if lock_version == "2.1":
            expected = [req.replace("foo[test]", "foo") for req in expected]
    exporter.export("requirements.txt", tmp_path, io)

    assert io.fetch_output() == "\n".join(expected) + "\n"


@pytest.mark.parametrize(
    ["fmt", "expected"],
    [
        (
            "constraints.txt",
            [
                f"bar==4.5.6 ; {MARKER_PY}",
                f"baz==7.8.9 ; {MARKER_PY}",
                f"foo==1.2.3 ; {MARKER_PY}",
            ],
        ),
        (
            "requirements.txt",
            [
                f"bar==4.5.6 ; {MARKER_PY}",
                f"bar[baz]==4.5.6 ; {MARKER_PY}",
                f"baz==7.8.9 ; {MARKER_PY}",
                f"foo==1.2.3 ; {MARKER_PY}",
            ],
        ),
    ],
)
@pytest.mark.parametrize("lock_version", ("1.1", "2.1"))
def test_exporter_omits_and_includes_extras_for_txt_formats(
    tmp_path: Path, poetry: Poetry, fmt: str, expected: list[str], lock_version: str
) -> None:
    lock_data = {
        "package": [
            {
                "name": "foo",
                "version": "1.2.3",
                "optional": False,
                "python-versions": "*",
                "dependencies": {
                    "bar": {
                        "extras": ["baz"],
                        "version": ">=0.1.0",
                    }
                },
            },
            {
                "name": "bar",
                "version": "4.5.6",
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
                "version": "7.8.9",
                "optional": False,
                "python-versions": "*",
            },
        ],
        "metadata": {
            "lock-version": lock_version,
            "python-versions": "*",
            "content-hash": "123456789",
            "files": {"foo": [], "bar": [], "baz": []},
        },
    }
    fix_lock_data(lock_data)
    poetry.locker.mock_lock_data(lock_data)  # type: ignore[attr-defined]
    set_package_requires(poetry)

    exporter = Exporter(poetry, NullIO())
    exporter.export(fmt, tmp_path, "exported.txt")

    with (tmp_path / "exported.txt").open(encoding="utf-8") as f:
        content = f.read()

    # It does not matter whether packages are exported with extras or not
    # because all dependencies are listed explicitly.
    if lock_version == "2.1":
        expected = [req for req in expected if not req.startswith("bar[baz]")]
    assert content == "\n".join(expected) + "\n"


@pytest.mark.parametrize("lock_version", ("1.1", "2.1"))
def test_exporter_prints_warning_for_constraints_txt_with_editable_packages(
    tmp_path: Path, poetry: Poetry, lock_version: str
) -> None:
    lock_data = {
        "package": [
            {
                "name": "foo",
                "version": "1.2.3",
                "optional": False,
                "python-versions": "*",
                "source": {
                    "type": "git",
                    "url": "https://github.com/foo/foo.git",
                    "reference": "123456",
                },
                "develop": True,
            },
            {
                "name": "bar",
                "version": "7.8.9",
                "optional": False,
                "python-versions": "*",
            },
            {
                "name": "baz",
                "version": "4.5.6",
                "optional": False,
                "python-versions": "*",
                "source": {
                    "type": "directory",
                    "url": "sample_project",
                    "reference": "",
                },
                "develop": True,
            },
        ],
        "metadata": {
            "lock-version": lock_version,
            "python-versions": "*",
            "content-hash": "123456789",
            "files": {"foo": [], "bar": [], "baz": []},
        },
    }
    fix_lock_data(lock_data)
    poetry.locker.mock_lock_data(lock_data)  # type: ignore[attr-defined]
    set_package_requires(poetry)

    io = BufferedIO()
    exporter = Exporter(poetry, io)
    exporter.export("constraints.txt", tmp_path, "constraints.txt")

    expected_error_out = (
        "<warning>Warning: foo is locked in develop (editable) mode, which is "
        "incompatible with the constraints.txt format.\n"
        "<warning>Warning: baz is locked in develop (editable) mode, which is "
        "incompatible with the constraints.txt format.\n"
    )

    assert io.fetch_error() == expected_error_out

    with (tmp_path / "constraints.txt").open(encoding="utf-8") as f:
        content = f.read()

    assert content == f"bar==7.8.9 ; {MARKER_PY}\n"


@pytest.mark.parametrize("lock_version", ("1.1", "2.1"))
def test_exporter_respects_package_sources(
    tmp_path: Path, poetry: Poetry, lock_version: str
) -> None:
    lock_data: dict[str, Any] = {
        "package": [
            {
                "name": "foo",
                "python-versions": ">=3.6",
                "version": "1.0.0",
                "optional": False,
                "dependencies": {},
                "source": {
                    "type": "url",
                    "url": "https://example.com/foo-darwin.whl",
                },
            },
            {
                "name": "foo",
                "python-versions": ">=3.6",
                "version": "1.0.0",
                "optional": False,
                "dependencies": {},
                "source": {
                    "type": "url",
                    "url": "https://example.com/foo-linux.whl",
                },
            },
        ],
        "metadata": {
            "lock-version": lock_version,
            "python-versions": "^3.6",
            "content-hash": (
                "832b13a88e5020c27cbcd95faa577bf0dbf054a65c023b45dc9442b640d414e6"
            ),
            "files": {
                "foo": [],
            },
        },
    }
    fix_lock_data(lock_data)
    if lock_version == "2.1":
        lock_data["package"][0]["markers"] = "sys_platform == 'darwin'"
        lock_data["package"][1]["markers"] = "sys_platform == 'linux'"
    poetry.locker.mock_lock_data(lock_data)  # type: ignore[attr-defined]
    root = poetry.package.with_dependency_groups([], only=True)
    root.python_versions = "^3.6"
    root.add_dependency(
        Factory.create_dependency(
            name="foo",
            constraint={
                "url": "https://example.com/foo-linux.whl",
                "platform": "linux",
            },
        )
    )
    root.add_dependency(
        Factory.create_dependency(
            name="foo",
            constraint={
                "url": "https://example.com/foo-darwin.whl",
                "platform": "darwin",
            },
        )
    )
    poetry._package = root

    io = BufferedIO()
    exporter = Exporter(poetry, NullIO())
    exporter.export("requirements.txt", tmp_path, io)

    expected = f"""\
foo @ https://example.com/foo-darwin.whl ; {MARKER_PY36} and {MARKER_DARWIN}
foo @ https://example.com/foo-linux.whl ; {MARKER_PY36} and {MARKER_LINUX}
"""

    assert io.fetch_output() == expected


@pytest.mark.parametrize("lock_version", ("1.1", "2.1"))
def test_exporter_tolerates_non_existent_extra(
    tmp_path: Path, poetry: Poetry, lock_version: str
) -> None:
    # foo actually has a 'bar' extra, but pyproject.toml mistakenly references a 'baz'
    # extra.
    lock_data = {
        "package": [
            {
                "name": "foo",
                "version": "1.2.3",
                "optional": False,
                "python-versions": "*",
                "dependencies": {
                    "bar": {
                        "version": ">=0.1.0",
                        "optional": True,
                        "markers": "extra == 'bar'",
                    }
                },
                "extras": {"bar": ["bar (>=0.1.0)"]},
            },
        ],
        "metadata": {
            "lock-version": lock_version,
            "python-versions": "*",
            "content-hash": "123456789",
            "files": {"foo": [], "bar": []},
        },
    }
    fix_lock_data(lock_data)
    poetry.locker.mock_lock_data(lock_data)  # type: ignore[attr-defined]
    root = poetry.package.with_dependency_groups([], only=True)
    root.add_dependency(
        Factory.create_dependency(
            name="foo", constraint={"version": "^1.2", "extras": ["baz"]}
        )
    )
    poetry._package = root

    exporter = Exporter(poetry, NullIO())
    exporter.export("requirements.txt", tmp_path, "requirements.txt")

    with (tmp_path / "requirements.txt").open(encoding="utf-8") as f:
        content = f.read()

    if lock_version == "1.1":
        expected = f"""\
foo[baz]==1.2.3 ; {MARKER_PY27} or {MARKER_PY36}
"""
    else:
        expected = f"""\
foo==1.2.3 ; {MARKER_PY27} or {MARKER_PY36}
"""
    assert content == expected


@pytest.mark.parametrize("lock_version", ("1.1", "2.1"))
def test_exporter_exports_extra_index_url_and_trusted_host(
    tmp_path: Path, poetry: Poetry, lock_version: str
) -> None:
    poetry.pool.add_repository(
        LegacyRepository(
            "custom",
            "http://example.com/simple",
        ),
        priority=Priority.EXPLICIT,
    )
    lock_data = {
        "package": [
            {
                "name": "foo",
                "version": "1.2.3",
                "optional": False,
                "python-versions": "*",
                "dependencies": {"bar": "*"},
            },
            {
                "name": "bar",
                "version": "4.5.6",
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
            "lock-version": lock_version,
            "python-versions": "*",
            "content-hash": "123456789",
            "files": {"foo": [], "bar": []},
        },
    }
    fix_lock_data(lock_data)
    poetry.locker.mock_lock_data(lock_data)  # type: ignore[attr-defined]
    set_package_requires(poetry)

    exporter = Exporter(poetry, NullIO())
    exporter.export("requirements.txt", tmp_path, "requirements.txt")

    with (tmp_path / "requirements.txt").open(encoding="utf-8") as f:
        content = f.read()

    expected = f"""\
--trusted-host example.com
--extra-index-url http://example.com/simple

bar==4.5.6 ; {MARKER_PY}
foo==1.2.3 ; {MARKER_PY}
"""
    assert content == expected


@pytest.mark.parametrize("lock_version", ("2.0", "2.1"))
def test_exporter_not_confused_by_extras_in_sub_dependencies(
    tmp_path: Path, poetry: Poetry, lock_version: str
) -> None:
    # Testcase derived from
    # https://github.com/python-poetry/poetry-plugin-export/issues/208
    lock_data: dict[str, Any] = {
        "package": [
            {
                "name": "typer",
                "python-versions": ">=3.6",
                "version": "0.9.0",
                "optional": False,
                "files": [],
                "dependencies": {
                    "click": ">=7.1.1,<9.0.0",
                    "colorama": {
                        "version": ">=0.4.3,<0.5.0",
                        "optional": True,
                        "markers": 'extra == "all"',
                    },
                },
                "extras": {"all": ["colorama (>=0.4.3,<0.5.0)"]},
            },
            {
                "name": "click",
                "python-versions": ">=3.7",
                "version": "8.1.3",
                "optional": False,
                "files": [],
                "dependencies": {
                    "colorama": {
                        "version": "*",
                        "markers": 'platform_system == "Windows"',
                    }
                },
            },
            {
                "name": "colorama",
                "python-versions": ">=3.7",
                "version": "0.4.6",
                "optional": False,
                "files": [],
            },
        ],
        "metadata": {
            "lock-version": lock_version,
            "python-versions": "^3.11",
            "content-hash": (
                "832b13a88e5020c27cbcd95faa577bf0dbf054a65c023b45dc9442b640d414e6"
            ),
        },
    }
    if lock_version == "2.1":
        for locked_package in lock_data["package"]:
            locked_package["groups"] = ["main"]
    poetry.locker.mock_lock_data(lock_data)  # type: ignore[attr-defined]
    root = poetry.package.with_dependency_groups([], only=True)
    root.python_versions = "^3.11"
    root.add_dependency(
        Factory.create_dependency(
            name="typer",
            constraint={"version": "^0.9.0", "extras": ["all"]},
        )
    )
    poetry._package = root

    io = BufferedIO()
    exporter = Exporter(poetry, NullIO())
    exporter.export("requirements.txt", tmp_path, io)

    if lock_version == "2.0":
        expected = """\
click==8.1.3 ; python_version >= "3.11" and python_version < "4.0"
colorama==0.4.6 ; python_version >= "3.11" and python_version < "4.0"
typer[all]==0.9.0 ; python_version >= "3.11" and python_version < "4.0"
"""
    else:
        expected = """\
click==8.1.3 ; python_version >= "3.11" and python_version < "4.0"
colorama==0.4.6 ; python_version >= "3.11" and python_version < "4.0"
typer==0.9.0 ; python_version >= "3.11" and python_version < "4.0"
"""
    assert io.fetch_output() == expected


@pytest.mark.parametrize(
    ("priorities", "expected"),
    [
        ([("custom-a", Priority.PRIMARY), ("custom-b", Priority.PRIMARY)], ("a", "b")),
        ([("custom-b", Priority.PRIMARY), ("custom-a", Priority.PRIMARY)], ("b", "a")),
        (
            [("custom-b", Priority.SUPPLEMENTAL), ("custom-a", Priority.PRIMARY)],
            ("a", "b"),
        ),
        ([("custom-b", Priority.EXPLICIT), ("custom-a", Priority.PRIMARY)], ("a", "b")),
        (
            [
                ("PyPI", Priority.PRIMARY),
                ("custom-a", Priority.PRIMARY),
                ("custom-b", Priority.PRIMARY),
            ],
            ("", "a", "b"),
        ),
        (
            [
                ("PyPI", Priority.EXPLICIT),
                ("custom-a", Priority.PRIMARY),
                ("custom-b", Priority.PRIMARY),
            ],
            ("", "a", "b"),
        ),
        (
            [
                ("custom-a", Priority.PRIMARY),
                ("custom-b", Priority.PRIMARY),
                ("PyPI", Priority.SUPPLEMENTAL),
            ],
            ("", "a", "b"),
        ),
    ],
)
@pytest.mark.parametrize("lock_version", ("1.1", "2.1"))
def test_exporter_index_urls(
    tmp_path: Path,
    poetry: Poetry,
    priorities: list[tuple[str, Priority]],
    expected: tuple[str, ...],
    lock_version: str,
) -> None:
    pypi = poetry.pool.repository("PyPI")
    poetry.pool.remove_repository("PyPI")
    for name, prio in priorities:
        if name.lower() == "pypi":
            repo = pypi
        else:
            repo = LegacyRepository(name, f"https://{name[-1]}.example.com/simple")
        poetry.pool.add_repository(repo, priority=prio)

    lock_data: dict[str, Any] = {
        "package": [
            {
                "name": "foo",
                "version": "1.2.3",
                "optional": False,
                "python-versions": "*",
                "source": {
                    "type": "legacy",
                    "url": "https://a.example.com/simple",
                    "reference": "",
                },
            },
            {
                "name": "bar",
                "version": "4.5.6",
                "optional": False,
                "python-versions": "*",
                "source": {
                    "type": "legacy",
                    "url": "https://b.example.com/simple",
                    "reference": "",
                },
            },
        ],
        "metadata": {
            "lock-version": lock_version,
            "python-versions": "*",
            "content-hash": "123456789",
            "files": {
                "foo": [{"name": "foo.whl", "hash": "12345"}],
                "bar": [{"name": "bar.whl", "hash": "67890"}],
            },
        },
    }
    fix_lock_data(lock_data)
    if lock_version == "2.1":
        lock_data["package"][0]["groups"] = ["dev"]
    poetry.locker.mock_lock_data(lock_data)  # type: ignore[attr-defined]
    set_package_requires(poetry, dev={"bar"})

    exporter = Exporter(poetry, NullIO())
    exporter.only_groups([MAIN_GROUP, "dev"])
    exporter.export("requirements.txt", tmp_path, "requirements.txt")

    with (tmp_path / "requirements.txt").open(encoding="utf-8") as f:
        content = f.read()

    expected_urls = [
        f"--extra-index-url https://{name[-1]}.example.com/simple"
        for name in expected[1:]
    ]
    if expected[0]:
        expected_urls = [
            f"--index-url https://{expected[0]}.example.com/simple",
            *expected_urls,
        ]
    url_string = "\n".join(expected_urls)

    expected_content = f"""\
{url_string}

bar==4.5.6 ; {MARKER_PY} \\
    --hash=sha256:67890
foo==1.2.3 ; {MARKER_PY} \\
    --hash=sha256:12345
"""

    assert content == expected_content


@pytest.mark.parametrize("lock_version", ("1.1", "2.1"))
def test_dependency_walk_error(
    tmp_path: Path, poetry: Poetry, lock_version: str
) -> None:
    """
    With lock file version 2.1 we can export lock files
    that resulted in a DependencyWalkerError with lower lock file versions.

    root
    ├── foo >=0 ; python_version < "3.9"
    ├── foo >=1 ; python_version >= "3.9"
    ├── bar ==1 ; python_version < "3.9"
    │   └── foo ==1 ; python_version < "3.9"
    └── bar ==2 ; python_version >= "3.9"
        └── foo ==2 ; python_version >= "3.9"

    Only considering the root dependency, foo 2 is a valid solution
    for all environments. However, due to bar depending on foo,
    foo 1 must be chosen for Python 3.8 and lower.
    """
    lock_data: dict[str, Any] = {
        "package": [
            {
                "name": "foo",
                "version": "1",
                "optional": False,
                "python-versions": "*",
            },
            {
                "name": "foo",
                "version": "2",
                "optional": False,
                "python-versions": "*",
            },
            {
                "name": "bar",
                "version": "1",
                "optional": False,
                "python-versions": "*",
                "dependencies": {"foo": "1"},
            },
            {
                "name": "bar",
                "version": "2",
                "optional": False,
                "python-versions": "*",
                "dependencies": {"foo": "2"},
            },
        ],
        "metadata": {
            "lock-version": lock_version,
            "python-versions": "*",
            "content-hash": "123456789",
            "files": {"foo": [], "bar": []},
        },
    }
    fix_lock_data(lock_data)
    if lock_version == "2.1":
        lock_data["package"][0]["markers"] = "python_version < '3.9'"
        lock_data["package"][1]["markers"] = "python_version >= '3.9'"
        lock_data["package"][2]["markers"] = "python_version < '3.9'"
        lock_data["package"][3]["markers"] = "python_version >= '3.9'"
    poetry.locker.mock_lock_data(lock_data)  # type: ignore[attr-defined]
    poetry.package.python_versions = "^3.8"
    poetry.package.add_dependency(
        Factory.create_dependency(
            name="foo", constraint={"version": ">=0", "python": "<3.9"}
        )
    )
    poetry.package.add_dependency(
        Factory.create_dependency(
            name="foo", constraint={"version": ">=1", "python": ">=3.9"}
        )
    )
    poetry.package.add_dependency(
        Factory.create_dependency(
            name="bar", constraint={"version": "1", "python": "<3.9"}
        )
    )
    poetry.package.add_dependency(
        Factory.create_dependency(
            name="bar", constraint={"version": "2", "python": ">=3.9"}
        )
    )

    exporter = Exporter(poetry, NullIO())
    if lock_version == "1.1":
        with pytest.raises(DependencyWalkerError):
            exporter.export("requirements.txt", tmp_path, "requirements.txt")
        return

    exporter.export("requirements.txt", tmp_path, "requirements.txt")

    with (tmp_path / "requirements.txt").open(encoding="utf-8") as f:
        content = f.read()

    expected = """\
bar==1 ; python_version >= "3.8" and python_version < "3.9"
bar==2 ; python_version >= "3.9" and python_version < "4.0"
foo==1 ; python_version >= "3.8" and python_version < "3.9"
foo==2 ; python_version >= "3.9" and python_version < "4.0"
"""

    assert content == expected
