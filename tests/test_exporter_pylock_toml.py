from __future__ import annotations

from typing import TYPE_CHECKING
from typing import Any

import pytest

from cleo.io.null_io import NullIO
from packaging.utils import canonicalize_name
from poetry.core.constraints.version import Version
from poetry.core.packages.dependency_group import MAIN_GROUP
from poetry.core.packages.package import Package
from poetry.factory import Factory
from poetry.packages import Locker as BaseLocker
from poetry.repositories import Repository

from poetry_plugin_export.exporter import Exporter


if TYPE_CHECKING:
    from pathlib import Path

    from poetry.poetry import Poetry
    from pytest_mock import MockerFixture


DEV_GROUP = canonicalize_name("dev")


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

    def _get_content_hash(self, *, with_dependency_groups: bool = True) -> str:
        return "123456789"


@pytest.fixture
def locker(fixture_root: Path) -> Locker:
    return Locker(fixture_root)


@pytest.fixture
def pypi_repo() -> Repository:
    repo = Repository("PyPI")
    foo = Package("foo", "1.0")
    foo.files = [
        {
            "file": "foo-1.0-py3-none-any.whl",
            "hash": "sha256:abcdef1234567890",
            "url": "https://example.org/foo-1.0-py3-none-any.whl",
            "upload_time": "2025-12-28T12:34:56.789Z",
            "size": 12345,
        },
        {
            "file": "foo-1.0.tar.gz",
            "hash": "sha256:0123456789abcdef",
            "url": "https://example.org/foo-1.0.tar.gz",
        },
    ]
    repo.add_package(foo)
    return repo


@pytest.fixture
def legacy_repositories() -> list[Repository]:
    repos = []
    for repo_name in ("legacy1", "legacy2"):
        repo = Repository(repo_name)
        repos.append(repo)
        for package_name in ("foo", "bar"):
            package = Package(
                package_name,
                "1.0",
                source_type="legacy",
                source_url=f"https://{repo_name}.org/simple",
                source_reference=repo_name,
            )
            package.files = [
                {
                    "file": f"{package_name}-1.0-py3-none-any.whl",
                    "hash": "sha256:abcdef1234567890",
                    "url": f"https://{repo_name}.org/{package_name}-1.0-py3-none-any.whl",
                },
                {
                    "file": f"{package_name}-1.0.tar.gz",
                    "hash": "sha256:0123456789abcdef",
                    "url": f"https://{repo_name}.org/{package_name}-1.0.tar.gz",
                    "upload_time": "2025-12-27T12:34:56.789Z",
                    "size": 42,
                },
            ]
            repo.add_package(package)
    return repos


@pytest.fixture
def poetry(
    fixture_root: Path,
    locker: Locker,
    pypi_repo: Repository,
    legacy_repositories: list[Repository],
) -> Poetry:
    p = Factory().create_poetry(fixture_root / "sample_project")
    p.package.python_versions = "*"
    p._locker = locker
    p.pool.remove_repository("PyPI")
    p.pool.add_repository(pypi_repo)
    for repo in legacy_repositories:
        p.pool.add_repository(repo)

    return p


@pytest.fixture(autouse=True)
def mock_poetry_version(mocker: MockerFixture) -> None:
    mocker.patch(
        "poetry_plugin_export.exporter.Exporter._get_poetry_version",
        return_value="2.3.0",
    )


def test_exporter_raises_error_on_old_poetry_version(
    mocker: MockerFixture, tmp_path: Path, poetry: Poetry
) -> None:
    mocker.patch(
        "poetry_plugin_export.exporter.Exporter._get_poetry_version",
        return_value="2.2.1",
    )

    lock_data = {"metadata": {"lock-version": "2.0"}}
    poetry.locker.mock_lock_data(lock_data)  # type: ignore[attr-defined]

    exporter = Exporter(poetry, NullIO())

    with pytest.raises(RuntimeError) as exc_info:
        exporter.export("pylock.toml", tmp_path, "pylock.toml")

    assert str(exc_info.value) == (
        "Exporting pylock.toml requires Poetry version 2.3.0 or higher."
    )


def test_exporter_raises_error_on_old_lock_version(
    tmp_path: Path, poetry: Poetry
) -> None:
    lock_data = {"metadata": {"lock-version": "2.0"}}
    poetry.locker.mock_lock_data(lock_data)  # type: ignore[attr-defined]

    exporter = Exporter(poetry, NullIO())

    with pytest.raises(RuntimeError) as exc_info:
        exporter.export("pylock.toml", tmp_path, "pylock.toml")

    assert str(exc_info.value) == (
        "Cannot export pylock.toml because the lock file is not at least version 2.1"
    )


def test_exporter_locks_exported_groups_and_extras(
    tmp_path: Path, poetry: Poetry
) -> None:
    lock_data = {"package": [], "metadata": {"lock-version": "2.1"}}
    poetry.locker.mock_lock_data(lock_data)  # type: ignore[attr-defined]

    exporter = Exporter(poetry, NullIO())
    exporter.only_groups([DEV_GROUP])
    exporter.with_extras([canonicalize_name("extra1"), canonicalize_name("extra2")])

    exporter.export("pylock.toml", tmp_path, "pylock.toml")

    with (tmp_path / "pylock.toml").open(encoding="utf-8") as f:
        content = f.read()

    expected = """\
lock-version = "1.0"
created-by = "poetry-plugin-export"
packages = []

[tool.poetry-plugin-export]
groups = ["dev"]
extras = ["extra1", "extra2"]
"""

    assert content == expected


@pytest.mark.parametrize(
    ("python_versions", "expected_python", "expected_marker"),
    [
        (">=3.9", ">=3.9", 'python_version >= "3.9"'),
        ("~3.9", ">=3.9,<3.10", 'python_version == "3.9"'),
        ("^3.9", ">=3.9,<4.0", 'python_version >= "3.9" and python_version < "4.0"'),
    ],
)
def test_exporter_python_constraint(
    tmp_path: Path,
    poetry: Poetry,
    python_versions: str,
    expected_python: str,
    expected_marker: str,
) -> None:
    poetry.package.python_versions = python_versions
    lock_data = {"package": [], "metadata": {"lock-version": "2.1"}}
    poetry.locker.mock_lock_data(lock_data)  # type: ignore[attr-defined]

    exporter = Exporter(poetry, NullIO())

    exporter.export("pylock.toml", tmp_path, "pylock.toml")

    with (tmp_path / "pylock.toml").open(encoding="utf-8") as f:
        content = f.read()

    expected_marker = expected_marker.replace('"', '\\"')
    expected = f"""\
lock-version = "1.0"
environments = ["{expected_marker}"]
requires-python = "{expected_python}"
created-by = "poetry-plugin-export"
packages = []

[tool.poetry-plugin-export]
groups = ["main"]
extras = []
"""

    assert content == expected


@pytest.mark.parametrize(
    ("python_versions", "expected_python", "expected_marker"),
    [
        (
            "~2.7 | ^3.9",
            ">=2.7,<2.8 || >=3.9,<4.0",
            'python_version == "2.7" or python_version >= "3.9" and python_version < "4.0"',
        ),
    ],
)
def test_exporter_does_not_write_invalid_python_constraint(
    tmp_path: Path,
    poetry: Poetry,
    python_versions: str,
    expected_python: str,
    expected_marker: str,
) -> None:
    poetry.package.python_versions = python_versions
    lock_data = {"package": [], "metadata": {"lock-version": "2.1"}}
    poetry.locker.mock_lock_data(lock_data)  # type: ignore[attr-defined]

    exporter = Exporter(poetry, NullIO())

    exporter.export("pylock.toml", tmp_path, "pylock.toml")

    with (tmp_path / "pylock.toml").open(encoding="utf-8") as f:
        content = f.read()

    expected_marker = expected_marker.replace('"', '\\"')
    expected = f"""\
lock-version = "1.0"
environments = ["{expected_marker}"]
# requires-python = "{expected_python}"
created-by = "poetry-plugin-export"
packages = []

[tool.poetry-plugin-export]
groups = ["main"]
extras = []
"""

    assert content == expected


def test_export_vcs_dependencies(tmp_path: Path, poetry: Poetry) -> None:
    lock_data = {
        "package": [
            {
                "name": "foo",
                "version": "1.2.3",
                "optional": False,
                "python-versions": "*",
                "groups": [MAIN_GROUP],
                "source": {
                    "type": "git",
                    "url": "https://github.com/foo/foo.git",
                    "reference": "123456",
                    "resolved_reference": "abcdef",
                },
            },
            {
                "name": "bar",
                "version": "2.3",
                "optional": False,
                "python-versions": "*",
                "groups": [MAIN_GROUP],
                "source": {
                    "type": "git",
                    "url": "https://github.com/bar/bar.git",
                    "reference": "123456",
                    "resolved_reference": "abcdef",
                    "subdirectory": "subdir",
                },
            },
        ],
        "metadata": {"lock-version": "2.1"},
    }
    poetry.locker.mock_lock_data(lock_data)  # type: ignore[attr-defined]

    exporter = Exporter(poetry, NullIO())

    exporter.export("pylock.toml", tmp_path, "pylock.toml")

    with (tmp_path / "pylock.toml").open(encoding="utf-8") as f:
        content = f.read()

    expected = """\
lock-version = "1.0"
created-by = "poetry-plugin-export"

[[packages]]
name = "foo"
version = "1.2.3"

[packages.vcs]
type = "git"
url = "https://github.com/foo/foo.git"
requested-revision = "123456"
commit-id = "abcdef"

[[packages]]
name = "bar"
version = "2.3"

[packages.vcs]
type = "git"
url = "https://github.com/bar/bar.git"
requested-revision = "123456"
commit-id = "abcdef"
subdirectory = "subdir"

[tool.poetry-plugin-export]
groups = ["main"]
extras = []
"""

    assert content == expected


def test_export_directory_dependencies(tmp_path: Path, poetry: Poetry) -> None:
    tmp_project = tmp_path / "tmp_project"
    tmp_project.mkdir()
    lock_data = {
        "package": [
            {
                "name": "simple_project",
                "version": "1.2.3",
                "optional": False,
                "python-versions": "*",
                "groups": [MAIN_GROUP],
                "source": {
                    "type": "directory",
                    "url": "simple_project",
                },
            },
            {
                "name": "tmp-project",
                "version": "1.2.3",
                "optional": False,
                "python-versions": "*",
                "develop": True,
                "groups": [MAIN_GROUP],
                "source": {
                    "type": "directory",
                    "url": tmp_project.as_posix(),
                },
            },
        ],
        "metadata": {"lock-version": "2.1"},
    }
    poetry.locker.mock_lock_data(lock_data)  # type: ignore[attr-defined]

    exporter = Exporter(poetry, NullIO())

    exporter.export("pylock.toml", tmp_path, "pylock.toml")

    with (tmp_path / "pylock.toml").open(encoding="utf-8") as f:
        content = f.read()

    expected = f"""\
lock-version = "1.0"
created-by = "poetry-plugin-export"

[[packages]]
name = "simple-project"

[packages.directory]
path = "{(poetry.locker.lock.parent / "simple_project").as_posix()}"

[[packages]]
name = "tmp-project"

[packages.directory]
path = "tmp_project"
editable = true

[tool.poetry-plugin-export]
groups = ["main"]
extras = []
"""

    assert content == expected


def test_export_file_dependencies(
    tmp_path: Path, poetry: Poetry, fixture_root: Path
) -> None:
    tmp_project = tmp_path / "files" / "tmp_project.zip"
    tmp_project.parent.mkdir()
    tmp_project.touch()
    lock_data = {
        "package": [
            {
                "name": "demo",
                "version": "0.1.0",
                "optional": False,
                "python-versions": "*",
                "groups": [MAIN_GROUP],
                "source": {
                    "type": "file",
                    "url": "distributions/demo-0.2.0-py3-none-any.whl",
                },
                "files": [
                    {
                        "file": "demo-0.2.0-py3-none-any.whl",
                        "hash": "sha256:abcdef1234567890",
                    }
                ],
            },
            {
                "name": "simple-project",
                "version": "1.2.3",
                "optional": False,
                "python-versions": "*",
                "develop": True,
                "groups": [MAIN_GROUP],
                "source": {
                    "type": "directory",
                    "url": "simple_project/dist/simple_project-0.1.0.tar.gz",
                },
                "files": [
                    {
                        "file": "simple_project-0.1.0.tar.gz",
                        "hash": "sha256:1234567890abcdef",
                    }
                ],
            },
            {
                "name": "tmp-project",
                "version": "3",
                "optional": False,
                "python-versions": "*",
                "groups": [MAIN_GROUP],
                "source": {
                    "type": "file",
                    "url": f"{tmp_project.as_posix()}",
                    "subdirectory": "sub",
                },
                "files": [
                    {
                        "file": "tmp_project.zip",
                        "hash": "sha256:fedcba0987654321",
                    }
                ],
            },
        ],
        "metadata": {"lock-version": "2.1"},
    }
    poetry.locker.mock_lock_data(lock_data)  # type: ignore[attr-defined]

    exporter = Exporter(poetry, NullIO())

    exporter.export("pylock.toml", tmp_path, "pylock.toml")

    with (tmp_path / "pylock.toml").open(encoding="utf-8") as f:
        content = f.read()

    expected = f"""\
lock-version = "1.0"
created-by = "poetry-plugin-export"

[[packages]]
name = "demo"
version = "0.1.0"
archive = {{path = "{fixture_root.as_posix()}/distributions/demo-0.2.0-py3-none-any.whl", hashes = {{sha256 = "abcdef1234567890"}}}}

[[packages]]
name = "simple-project"

[packages.directory]
path = "{(poetry.locker.lock.parent / "simple_project" / "dist" / "simple_project-0.1.0.tar.gz").as_posix()}"
editable = true

[[packages]]
name = "tmp-project"
version = "3"
archive = {{path = "files/tmp_project.zip", hashes = {{sha256 = "fedcba0987654321"}}, subdirectory = "sub"}}

[tool.poetry-plugin-export]
groups = ["main"]
extras = []
"""

    assert content == expected


def test_export_url_dependencies(tmp_path: Path, poetry: Poetry) -> None:
    lock_data = {
        "package": [
            {
                "name": "foo",
                "version": "1.0",
                "optional": False,
                "python-versions": "*",
                "groups": [MAIN_GROUP],
                "source": {
                    "type": "url",
                    "url": "https://example.org/foo-1.0-py3-none-any.whl",
                },
                "files": [
                    {
                        "file": "foo-1.0-py3-none-any.whl",
                        "hash": "sha256:abcdef1234567890",
                    }
                ],
            },
            {
                "name": "bar",
                "version": "3",
                "optional": False,
                "python-versions": "*",
                "groups": [MAIN_GROUP],
                "source": {
                    "type": "url",
                    "url": "https://example.org/bar.zip#subdir=sub",
                    "subdirectory": "sub",
                },
                "files": [
                    {
                        "file": "bar.zip",
                        "hash": "sha256:fedcba0987654321",
                    }
                ],
            },
        ],
        "metadata": {"lock-version": "2.1"},
    }
    poetry.locker.mock_lock_data(lock_data)  # type: ignore[attr-defined]

    exporter = Exporter(poetry, NullIO())

    exporter.export("pylock.toml", tmp_path, "pylock.toml")

    with (tmp_path / "pylock.toml").open(encoding="utf-8") as f:
        content = f.read()

    expected = """\
lock-version = "1.0"
created-by = "poetry-plugin-export"

[[packages]]
name = "foo"
version = "1.0"
archive = {url = "https://example.org/foo-1.0-py3-none-any.whl", hashes = {sha256 = "abcdef1234567890"}}

[[packages]]
name = "bar"
version = "3"
archive = {url = "https://example.org/bar.zip#subdir=sub", hashes = {sha256 = "fedcba0987654321"}, subdirectory = "sub"}

[tool.poetry-plugin-export]
groups = ["main"]
extras = []
"""

    assert content == expected


def test_export_pypi_dependencies(tmp_path: Path, poetry: Poetry) -> None:
    lock_data = {
        "package": [
            {
                "name": "foo",
                "version": "1.0",
                "optional": False,
                "python-versions": "*",
                "groups": [MAIN_GROUP],
                "files": [
                    {
                        "file": "foo-1.0-py3-none-any.whl",
                        "hash": "sha256:abcdef1234567890",
                    },
                    {
                        "file": "foo-1.0.tar.gz",
                        "hash": "sha256:0123456789abcdef",
                    },
                ],
            },
        ],
        "metadata": {"lock-version": "2.1"},
    }
    poetry.locker.mock_lock_data(lock_data)  # type: ignore[attr-defined]

    exporter = Exporter(poetry, NullIO())

    exporter.export("pylock.toml", tmp_path, "pylock.toml")

    with (tmp_path / "pylock.toml").open(encoding="utf-8") as f:
        content = f.read()

    expected = """\
lock-version = "1.0"
created-by = "poetry-plugin-export"

[[packages]]
name = "foo"
version = "1.0"
index = "https://pypi.org/simple"
sdist = {name = "foo-1.0.tar.gz", url = "https://example.org/foo-1.0.tar.gz", hashes = {sha256 = "0123456789abcdef"}}
wheels = [
    {name = "foo-1.0-py3-none-any.whl", url = "https://example.org/foo-1.0-py3-none-any.whl", upload-time = 2025-12-28T12:34:56.789000Z, size = 12345, hashes = {sha256 = "abcdef1234567890"}},
]

[tool.poetry-plugin-export]
groups = ["main"]
extras = []
"""

    assert content == expected


def test_export_pypi_dependencies_sdist_only(tmp_path: Path, poetry: Poetry) -> None:
    lock_data = {
        "package": [
            {
                "name": "foo",
                "version": "1.0",
                "optional": False,
                "python-versions": "*",
                "groups": [MAIN_GROUP],
                "files": [
                    {
                        "file": "foo-1.0.tar.gz",
                        "hash": "sha256:0123456789abcdef",
                    },
                ],
            },
        ],
        "metadata": {"lock-version": "2.1"},
    }
    poetry.locker.mock_lock_data(lock_data)  # type: ignore[attr-defined]

    poetry.pool.repository("PyPI").package("foo", Version.parse("1.0")).files = [
        {
            "file": "foo-1.0.tar.gz",
            "hash": "sha256:0123456789abcdef",
            "url": "https://example.org/foo-1.0.tar.gz",
        },
    ]

    exporter = Exporter(poetry, NullIO())

    exporter.export("pylock.toml", tmp_path, "pylock.toml")

    with (tmp_path / "pylock.toml").open(encoding="utf-8") as f:
        content = f.read()

    expected = """\
lock-version = "1.0"
created-by = "poetry-plugin-export"

[[packages]]
name = "foo"
version = "1.0"
index = "https://pypi.org/simple"
sdist = {name = "foo-1.0.tar.gz", url = "https://example.org/foo-1.0.tar.gz", hashes = {sha256 = "0123456789abcdef"}}

[tool.poetry-plugin-export]
groups = ["main"]
extras = []
"""

    assert content == expected


def test_export_pypi_dependencies_wheel_only(tmp_path: Path, poetry: Poetry) -> None:
    lock_data = {
        "package": [
            {
                "name": "foo",
                "version": "1.0",
                "optional": False,
                "python-versions": "*",
                "groups": [MAIN_GROUP],
                "files": [
                    {
                        "file": "foo-1.0-py3-none-any.whl",
                        "hash": "sha256:abcdef1234567890",
                    },
                ],
            },
        ],
        "metadata": {"lock-version": "2.1"},
    }
    poetry.locker.mock_lock_data(lock_data)  # type: ignore[attr-defined]

    poetry.pool.repository("PyPI").package("foo", Version.parse("1.0")).files = [
        {
            "file": "foo-1.0-py3-none-any.whl",
            "hash": "sha256:abcdef1234567890",
            "url": "https://example.org/foo-1.0-py3-none-any.whl",
        },
    ]

    exporter = Exporter(poetry, NullIO())

    exporter.export("pylock.toml", tmp_path, "pylock.toml")

    with (tmp_path / "pylock.toml").open(encoding="utf-8") as f:
        content = f.read()

    expected = """\
lock-version = "1.0"
created-by = "poetry-plugin-export"

[[packages]]
name = "foo"
version = "1.0"
index = "https://pypi.org/simple"
wheels = [
    {name = "foo-1.0-py3-none-any.whl", url = "https://example.org/foo-1.0-py3-none-any.whl", hashes = {sha256 = "abcdef1234567890"}},
]

[tool.poetry-plugin-export]
groups = ["main"]
extras = []
"""

    assert content == expected


def test_export_pypi_dependencies_multiple_wheels(
    tmp_path: Path, poetry: Poetry
) -> None:
    lock_data = {
        "package": [
            {
                "name": "foo",
                "version": "1.0",
                "optional": False,
                "python-versions": "*",
                "groups": [MAIN_GROUP],
                "files": [
                    {
                        "file": "foo-1.0-py2-none-any.whl",
                        "hash": "sha256:abcdef1234567891",
                    },
                    {
                        "file": "foo-1.0-py3-none-any.whl",
                        "hash": "sha256:abcdef1234567890",
                    },
                ],
            },
        ],
        "metadata": {"lock-version": "2.1"},
    }
    poetry.locker.mock_lock_data(lock_data)  # type: ignore[attr-defined]

    poetry.pool.repository("PyPI").package("foo", Version.parse("1.0")).files = [
        {
            "file": "foo-1.0-py2-none-any.whl",
            "hash": "sha256:abcdef1234567891",
            "url": "https://example.org/foo-1.0-py2-none-any.whl",
        },
        {
            "file": "foo-1.0-py3-none-any.whl",
            "hash": "sha256:abcdef1234567890",
            "url": "https://example.org/foo-1.0-py3-none-any.whl",
        },
    ]

    exporter = Exporter(poetry, NullIO())

    exporter.export("pylock.toml", tmp_path, "pylock.toml")

    with (tmp_path / "pylock.toml").open(encoding="utf-8") as f:
        content = f.read()

    expected = """\
lock-version = "1.0"
created-by = "poetry-plugin-export"

[[packages]]
name = "foo"
version = "1.0"
index = "https://pypi.org/simple"
wheels = [
    {name = "foo-1.0-py2-none-any.whl", url = "https://example.org/foo-1.0-py2-none-any.whl", hashes = {sha256 = "abcdef1234567891"}},
    {name = "foo-1.0-py3-none-any.whl", url = "https://example.org/foo-1.0-py3-none-any.whl", hashes = {sha256 = "abcdef1234567890"}},
]

[tool.poetry-plugin-export]
groups = ["main"]
extras = []
"""

    assert content == expected


def test_export_legacy_repo_dependencies(tmp_path: Path, poetry: Poetry) -> None:
    lock_data = {
        "package": [
            {
                "name": "foo",
                "version": "1.0",
                "optional": False,
                "python-versions": "*",
                "groups": [MAIN_GROUP],
                "source": {
                    "type": "legacy",
                    "url": "https://legacy1.org/simple",
                    "reference": "legacy1",
                },
                "files": [
                    {
                        "file": "foo-1.0-py3-none-any.whl",
                        "hash": "sha256:abcdef1234567890",
                    },
                    {
                        "file": "foo-1.0.tar.gz",
                        "hash": "sha256:0123456789abcdef",
                    },
                ],
            },
            {
                "name": "bar",
                "version": "1.0",
                "optional": False,
                "python-versions": "*",
                "groups": [MAIN_GROUP],
                "source": {
                    "type": "legacy",
                    "url": "https://legacy2.org/simple",
                    "reference": "legacy2",
                },
                "files": [
                    {
                        "file": "bar-1.0-py3-none-any.whl",
                        "hash": "sha256:abcdef1234567890",
                    },
                    {
                        "file": "bar-1.0.tar.gz",
                        "hash": "sha256:0123456789abcdef",
                    },
                ],
            },
        ],
        "metadata": {"lock-version": "2.1"},
    }
    poetry.locker.mock_lock_data(lock_data)  # type: ignore[attr-defined]

    exporter = Exporter(poetry, NullIO())

    exporter.export("pylock.toml", tmp_path, "pylock.toml")

    with (tmp_path / "pylock.toml").open(encoding="utf-8") as f:
        content = f.read()

    expected = """\
lock-version = "1.0"
created-by = "poetry-plugin-export"

[[packages]]
name = "foo"
version = "1.0"
index = "https://legacy1.org/simple"
sdist = {name = "foo-1.0.tar.gz", url = "https://legacy1.org/foo-1.0.tar.gz", upload-time = 2025-12-27T12:34:56.789000Z, size = 42, hashes = {sha256 = "0123456789abcdef"}}
wheels = [
    {name = "foo-1.0-py3-none-any.whl", url = "https://legacy1.org/foo-1.0-py3-none-any.whl", hashes = {sha256 = "abcdef1234567890"}},
]

[[packages]]
name = "bar"
version = "1.0"
index = "https://legacy2.org/simple"
sdist = {name = "bar-1.0.tar.gz", url = "https://legacy2.org/bar-1.0.tar.gz", upload-time = 2025-12-27T12:34:56.789000Z, size = 42, hashes = {sha256 = "0123456789abcdef"}}
wheels = [
    {name = "bar-1.0-py3-none-any.whl", url = "https://legacy2.org/bar-1.0-py3-none-any.whl", hashes = {sha256 = "abcdef1234567890"}},
]

[tool.poetry-plugin-export]
groups = ["main"]
extras = []
"""

    assert content == expected


@pytest.mark.parametrize(
    ("groups", "extras", "marker", "expected"),
    [
        ({"main"}, set(), 'python_version >= "3.6"', 'python_version >= "3.6"'),
        ({"other"}, set(), 'python_version >= "3.6"', ""),
        (
            {"main"},
            set(),
            {"main": 'python_version >= "3.6"'},
            'python_version >= "3.6"',
        ),
        ({"dev"}, set(), {"main": 'python_version >= "3.6"'}, "*"),
        (
            {"dev"},
            set(),
            {"main": 'python_version >= "3.6"', "dev": 'python_version < "3.6"'},
            'python_version < "3.6"',
        ),
        (
            {"main", "dev"},
            set(),
            {"main": 'python_version >= "3.6"', "dev": 'python_version < "3.6"'},
            "*",
        ),
        (
            {"main", "dev"},
            set(),
            {"main": 'python_version >= "3.6"', "dev": 'sys_platform == "linux"'},
            'python_version >= "3.6" or sys_platform == "linux"',
        ),
        # extras
        ({"main"}, {}, 'python_version >= "3.6" and extra == "extra1"', ""),
        (
            {"main"},
            {},
            'python_version >= "3.6" or extra == "extra1"',
            'python_version >= "3.6"',
        ),
        (
            {"main"},
            {},
            'python_version >= "3.6" and extra != "extra1"',
            'python_version >= "3.6"',
        ),
        (
            {"main"},
            {"extra1"},
            'python_version >= "3.6" and extra == "extra1"',
            'python_version >= "3.6"',
        ),
        (
            {"main"},
            {"extra1"},
            'python_version >= "3.6" or extra == "extra1"',
            'python_version >= "3.6"',
        ),
        ({"main"}, {"extra1"}, 'python_version >= "3.6" and extra != "extra1"', ""),
    ],
)
def test_export_markers(
    tmp_path: Path,
    poetry: Poetry,
    groups: set[str],
    extras: set[str],
    marker: str | dict[str, str],
    expected: str,
) -> None:
    lock_data = {
        "package": [
            {
                "name": "foo",
                "version": "1.0",
                "optional": False,
                "python-versions": "*",
                "groups": [MAIN_GROUP, DEV_GROUP],
                "markers": marker,
                "source": {
                    "type": "url",
                    "url": "https://example.org/foo-1.0-py3-none-any.whl",
                },
                "files": [
                    {
                        "file": "foo-1.0-py3-none-any.whl",
                        "hash": "sha256:abcdef1234567890",
                    }
                ],
            },
        ],
        "metadata": {"lock-version": "2.1"},
    }
    poetry.locker.mock_lock_data(lock_data)  # type: ignore[attr-defined]

    exporter = Exporter(poetry, NullIO())
    exporter.only_groups({canonicalize_name(g) for g in groups})
    if extras:
        exporter.with_extras({canonicalize_name(e) for e in extras})

    exporter.export("pylock.toml", tmp_path, "pylock.toml")

    with (tmp_path / "pylock.toml").open(encoding="utf-8") as f:
        content = f.read()

    match expected:
        case "":
            assert 'name = "foo"' not in content
        case "*":
            assert 'name = "foo"' in content.splitlines()
            assert "marker = " not in content
        case _:
            expected = expected.replace('"', '\\"')
            assert f'marker = "{expected}"' in content.splitlines()


@pytest.mark.parametrize(
    ("python_versions", "expected"),
    [
        (">=3.9", ">=3.9"),
        ("*", None),
        ("~2.7 | ^3.9", "# >=2.7,<2.8 || >=3.9,<4.0"),
    ],
)
def test_export_requires_python(
    tmp_path: Path, poetry: Poetry, python_versions: str, expected: str | None
) -> None:
    lock_data = {
        "package": [
            {
                "name": "foo",
                "version": "1.0",
                "optional": False,
                "python-versions": python_versions,
                "groups": [MAIN_GROUP],
                "source": {
                    "type": "url",
                    "url": "https://example.org/foo-1.0-py3-none-any.whl",
                },
                "files": [
                    {
                        "file": "foo-1.0-py3-none-any.whl",
                        "hash": "sha256:abcdef1234567890",
                    }
                ],
            },
        ],
        "metadata": {"lock-version": "2.1"},
    }
    poetry.locker.mock_lock_data(lock_data)  # type: ignore[attr-defined]

    exporter = Exporter(poetry, NullIO())

    exporter.export("pylock.toml", tmp_path, "pylock.toml")

    with (tmp_path / "pylock.toml").open(encoding="utf-8") as f:
        content = f.read()

    if expected is None:
        assert "requires-python" not in content
    else:
        prefix = "# " if expected.startswith("#") else ""
        expected = expected.removeprefix("# ")
        assert f'{prefix}requires-python = "{expected}"' in content.splitlines()
