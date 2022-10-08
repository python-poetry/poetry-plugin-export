from __future__ import annotations

import shutil

from typing import TYPE_CHECKING
from unittest.mock import Mock

import pytest

from poetry.core.packages.dependency_group import MAIN_GROUP
from poetry.core.packages.package import Package

from poetry_plugin_export.exporter import Exporter
from tests.markers import MARKER_PY


if TYPE_CHECKING:
    from pathlib import Path

    from _pytest.monkeypatch import MonkeyPatch
    from cleo.testers.command_tester import CommandTester
    from poetry.poetry import Poetry
    from poetry.repositories import Repository

    from tests.types import CommandTesterFactory
    from tests.types import ProjectFactory


PYPROJECT_CONTENT = """\
[tool.poetry]
name = "simple-project"
version = "1.2.3"
description = "Some description."
authors = [
    "Sébastien Eustace <sebastien@eustace.io>"
]
license = "MIT"

readme = "README.rst"

homepage = "https://python-poetry.org"
repository = "https://github.com/python-poetry/poetry"
documentation = "https://python-poetry.org/docs"

keywords = ["packaging", "dependency", "poetry"]

classifiers = [
    "Topic :: Software Development :: Build Tools",
    "Topic :: Software Development :: Libraries :: Python Modules"
]

# Requirements
[tool.poetry.dependencies]
python = "~2.7 || ^3.6"
foo = "^1.0"
bar = { version = "^1.1", optional = true }
qux = { version = "^1.2", optional = true }

[tool.poetry.group.dev.dependencies]
baz = "^2.0"

[tool.poetry.group.opt]
optional = true

[tool.poetry.group.opt.dependencies]
opt = "^2.2"


[tool.poetry.extras]
feature_bar = ["bar"]
feature_qux = ["qux"]
"""


@pytest.fixture(autouse=True)
def setup(repo: Repository) -> None:
    repo.add_package(Package("foo", "1.0.0"))
    repo.add_package(Package("bar", "1.1.0"))
    repo.add_package(Package("baz", "2.0.0"))
    repo.add_package(Package("opt", "2.2.0"))
    repo.add_package(Package("qux", "1.2.0"))


@pytest.fixture
def poetry(project_factory: ProjectFactory) -> Poetry:
    return project_factory(name="export", pyproject_content=PYPROJECT_CONTENT)


@pytest.fixture
def tester(
    command_tester_factory: CommandTesterFactory, poetry: Poetry
) -> CommandTester:
    return command_tester_factory("export", poetry=poetry)


def _export_requirements(tester: CommandTester, poetry: Poetry, tmp_path: Path) -> None:
    from tests.helpers import as_cwd

    with as_cwd(tmp_path):
        tester.execute("--format requirements.txt --output requirements.txt")

    requirements = tmp_path / "requirements.txt"
    assert requirements.exists()

    with requirements.open(encoding="utf-8") as f:
        content = f.read()

    assert poetry.locker.lock.exists()

    expected = f"""\
foo==1.0.0 ; {MARKER_PY}
"""

    assert content == expected


def test_export_exports_requirements_txt_file_locks_if_no_lock_file(
    tester: CommandTester, poetry: Poetry, tmp_path: Path
) -> None:
    assert not poetry.locker.lock.exists()
    _export_requirements(tester, poetry, tmp_path)
    assert "The lock file does not exist. Locking." in tester.io.fetch_error()


def test_export_exports_requirements_txt_uses_lock_file(
    tester: CommandTester, poetry: Poetry, tmp_path: Path, do_lock: None
) -> None:
    _export_requirements(tester, poetry, tmp_path)
    assert "The lock file does not exist. Locking." not in tester.io.fetch_error()


def test_export_fails_on_invalid_format(tester: CommandTester, do_lock: None) -> None:
    with pytest.raises(ValueError):
        tester.execute("--format invalid")


def test_export_prints_to_stdout_by_default(
    tester: CommandTester, do_lock: None
) -> None:
    tester.execute("--format requirements.txt")
    expected = f"""\
foo==1.0.0 ; {MARKER_PY}
"""
    assert tester.io.fetch_output() == expected


def test_export_uses_requirements_txt_format_by_default(
    tester: CommandTester, do_lock: None
) -> None:
    tester.execute()
    expected = f"""\
foo==1.0.0 ; {MARKER_PY}
"""
    assert tester.io.fetch_output() == expected


@pytest.mark.parametrize(
    "options, expected",
    [
        ("", f"foo==1.0.0 ; {MARKER_PY}\n"),
        ("--with dev", f"baz==2.0.0 ; {MARKER_PY}\nfoo==1.0.0 ; {MARKER_PY}\n"),
        ("--with opt", f"foo==1.0.0 ; {MARKER_PY}\nopt==2.2.0 ; {MARKER_PY}\n"),
        (
            "--with dev,opt",
            (
                f"baz==2.0.0 ; {MARKER_PY}\nfoo==1.0.0 ; {MARKER_PY}\nopt==2.2.0 ;"
                f" {MARKER_PY}\n"
            ),
        ),
        (f"--without {MAIN_GROUP}", "\n"),
        ("--without dev", f"foo==1.0.0 ; {MARKER_PY}\n"),
        ("--without opt", f"foo==1.0.0 ; {MARKER_PY}\n"),
        (f"--without {MAIN_GROUP},dev,opt", "\n"),
        (f"--only {MAIN_GROUP}", f"foo==1.0.0 ; {MARKER_PY}\n"),
        ("--only dev", f"baz==2.0.0 ; {MARKER_PY}\n"),
        (
            f"--only {MAIN_GROUP},dev",
            f"baz==2.0.0 ; {MARKER_PY}\nfoo==1.0.0 ; {MARKER_PY}\n",
        ),
    ],
)
def test_export_groups(
    tester: CommandTester, do_lock: None, options: str, expected: str
) -> None:
    tester.execute(options)
    assert tester.io.fetch_output() == expected


@pytest.mark.parametrize(
    "extras, expected",
    [
        (
            "feature_bar",
            f"""\
bar==1.1.0 ; {MARKER_PY}
foo==1.0.0 ; {MARKER_PY}
""",
        ),
        (
            "feature_bar feature_qux",
            f"""\
bar==1.1.0 ; {MARKER_PY}
foo==1.0.0 ; {MARKER_PY}
qux==1.2.0 ; {MARKER_PY}
""",
        ),
    ],
)
def test_export_includes_extras_by_flag(
    tester: CommandTester, do_lock: None, extras: str, expected: str
) -> None:
    tester.execute(f"--format requirements.txt --extras '{extras}'")
    assert tester.io.fetch_output() == expected


def test_export_reports_invalid_extras(tester: CommandTester, do_lock: None) -> None:
    with pytest.raises(ValueError) as error:
        tester.execute("--format requirements.txt --extras 'SUS AMONGUS'")
    expected = "Extra [amongus, sus] is not specified."
    assert str(error.value) == expected


def test_export_with_urls(
    monkeypatch: MonkeyPatch, tester: CommandTester, poetry: Poetry
) -> None:
    """
    We are just validating that the option gets passed. The option itself is tested in
    the Exporter test.
    """
    mock_export = Mock()
    monkeypatch.setattr(Exporter, "with_urls", mock_export)
    tester.execute("--without-urls")
    mock_export.assert_called_once_with(False)


def test_export_exports_constraints_txt_with_warnings(
    tmp_path: Path,
    fixture_root: Path,
    project_factory: ProjectFactory,
    command_tester_factory: CommandTesterFactory,
) -> None:
    # On Windows we have to make sure that the path dependency and the pyproject.toml
    # are on the same drive, otherwise locking fails.
    # (in our CI fixture_root is on D:\ but temp_path is on C:\)
    editable_dep_path = tmp_path / "project_with_nested_local"
    shutil.copytree(fixture_root / "project_with_nested_local", editable_dep_path)

    pyproject_content = f"""\
[tool.poetry]
name = "simple-project"
version = "1.2.3"
description = "Some description."
authors = [
    "Sébastien Eustace <sebastien@eustace.io>"
]

[tool.poetry.dependencies]
python = "^3.6"
baz = ">1.0"
project-with-nested-local = {{ path = "{editable_dep_path.as_posix()}", \
develop = true }}
"""
    poetry = project_factory(name="export", pyproject_content=pyproject_content)
    tester = command_tester_factory("export", poetry=poetry)
    tester.execute("--format constraints.txt")

    develop_warning = (
        "Warning: project-with-nested-local is locked in develop (editable) mode, which"
        " is incompatible with the constraints.txt format.\n"
    )
    expected = 'baz==2.0.0 ; python_version >= "3.6" and python_version < "4.0"\n'

    assert develop_warning in tester.io.fetch_error()
    assert tester.io.fetch_output() == expected
