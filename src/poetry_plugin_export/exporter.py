from __future__ import annotations

import contextlib
import itertools
import urllib.parse

from datetime import datetime
from functools import partialmethod
from importlib import metadata
from typing import TYPE_CHECKING
from typing import Any

from cleo.io.io import IO
from poetry.core.constraints.version.version import Version
from poetry.core.packages.dependency_group import MAIN_GROUP
from poetry.core.packages.directory_dependency import DirectoryDependency
from poetry.core.packages.file_dependency import FileDependency
from poetry.core.packages.url_dependency import URLDependency
from poetry.core.packages.utils.utils import create_nested_marker
from poetry.core.packages.vcs_dependency import VCSDependency
from poetry.core.version.markers import parse_marker
from poetry.repositories.http_repository import HTTPRepository

from poetry_plugin_export.walker import get_project_dependency_packages
from poetry_plugin_export.walker import get_project_dependency_packages2


if TYPE_CHECKING:
    from collections.abc import Collection
    from collections.abc import Iterable
    from pathlib import Path
    from typing import ClassVar

    from packaging.utils import NormalizedName
    from poetry.core.packages.package import PackageFile
    from poetry.poetry import Poetry


class Exporter:
    """
    Exporter class to export a lock file to alternative formats.
    """

    FORMAT_CONSTRAINTS_TXT = "constraints.txt"
    FORMAT_REQUIREMENTS_TXT = "requirements.txt"
    FORMAT_PYLOCK_TOML = "pylock.toml"
    ALLOWED_HASH_ALGORITHMS = ("sha256", "sha384", "sha512")

    EXPORT_METHODS: ClassVar[dict[str, str]] = {
        FORMAT_CONSTRAINTS_TXT: "_export_constraints_txt",
        FORMAT_REQUIREMENTS_TXT: "_export_requirements_txt",
        FORMAT_PYLOCK_TOML: "_export_pylock_toml",
    }

    def __init__(self, poetry: Poetry, io: IO) -> None:
        self._poetry = poetry
        self._io = io
        self._with_hashes = True
        self._with_credentials = False
        self._with_urls = True
        self._extras: Collection[NormalizedName] = ()
        self._groups: Iterable[NormalizedName] = [MAIN_GROUP]

    @classmethod
    def is_format_supported(cls, fmt: str) -> bool:
        return fmt in cls.EXPORT_METHODS

    def with_extras(self, extras: Collection[NormalizedName]) -> Exporter:
        self._extras = extras

        return self

    def only_groups(self, groups: Iterable[NormalizedName]) -> Exporter:
        self._groups = groups

        return self

    def with_urls(self, with_urls: bool = True) -> Exporter:
        self._with_urls = with_urls

        return self

    def with_hashes(self, with_hashes: bool = True) -> Exporter:
        self._with_hashes = with_hashes

        return self

    def with_credentials(self, with_credentials: bool = True) -> Exporter:
        self._with_credentials = with_credentials

        return self

    def export(self, fmt: str, cwd: Path, output: IO | str) -> None:
        if not self.is_format_supported(fmt):
            raise ValueError(f"Invalid export format: {fmt}")

        out_dir = cwd
        if isinstance(output, str):
            out_dir = (cwd / output).parent
        content = getattr(self, self.EXPORT_METHODS[fmt])(out_dir)

        if isinstance(output, IO):
            output.write(content)
        else:
            with (cwd / output).open("w", encoding="utf-8") as txt:
                txt.write(content)

    def _export_generic_txt(
        self, out_dir: Path, with_extras: bool, allow_editable: bool
    ) -> str:
        from poetry.core.packages.utils.utils import path_to_url

        indexes = set()
        content = ""
        dependency_lines = set()

        python_marker = parse_marker(
            create_nested_marker(
                "python_version", self._poetry.package.python_constraint
            )
        )
        if self._poetry.locker.is_locked_groups_and_markers():
            dependency_package_iterator = get_project_dependency_packages2(
                self._poetry.locker,
                project_python_marker=python_marker,
                groups=set(self._groups),
                extras=self._extras,
            )
        else:
            root = self._poetry.package.with_dependency_groups(
                list(self._groups), only=True
            )
            dependency_package_iterator = get_project_dependency_packages(
                self._poetry.locker,
                project_requires=root.all_requires,
                root_package_name=root.name,
                project_python_marker=python_marker,
                extras=self._extras,
            )

        for dependency_package in dependency_package_iterator:
            line = ""

            if not with_extras:
                dependency_package = dependency_package.without_features()

            dependency = dependency_package.dependency
            package = dependency_package.package

            if package.develop and not allow_editable:
                self._io.write_error_line(
                    f"<warning>Warning: {package.pretty_name} is locked in develop"
                    " (editable) mode, which is incompatible with the"
                    " constraints.txt format.</warning>"
                )
                continue

            requirement = dependency.to_pep_508(with_extras=False, resolved=True)
            is_direct_local_reference = (
                dependency.is_file() or dependency.is_directory()
            )
            is_direct_remote_reference = dependency.is_vcs() or dependency.is_url()

            if is_direct_remote_reference:
                line = requirement
            elif is_direct_local_reference:
                assert dependency.source_url is not None
                dependency_uri = path_to_url(dependency.source_url)
                if package.develop:
                    line = f"-e {dependency_uri}"
                else:
                    line = f"{package.complete_name} @ {dependency_uri}"
            else:
                line = f"{package.complete_name}=={package.version}"

            if not is_direct_remote_reference and ";" in requirement:
                markers = requirement.split(";", 1)[1].strip()
                if markers:
                    line += f" ; {markers}"

            if (
                not is_direct_remote_reference
                and not is_direct_local_reference
                and package.source_url
            ):
                indexes.add(package.source_url.rstrip("/"))

            if package.files and self._with_hashes:
                hashes = []
                for f in package.files:
                    h = f["hash"]
                    algorithm = "sha256"
                    if ":" in h:
                        algorithm, h = h.split(":")

                        if algorithm not in self.ALLOWED_HASH_ALGORITHMS:
                            continue

                    hashes.append(f"{algorithm}:{h}")

                hashes.sort()

                for h in hashes:
                    line += f" \\\n    --hash={h}"

            dependency_lines.add(line)

        content += "\n".join(sorted(dependency_lines))
        content += "\n"

        if indexes and self._with_urls:
            # If we have extra indexes, we add them to the beginning of the output
            indexes_header = ""
            has_pypi_repository = any(
                r.name.lower() == "pypi" for r in self._poetry.pool.all_repositories
            )
            # Iterate over repositories so that we get the repository with the highest
            # priority first so that --index-url comes before --extra-index-url
            for repository in self._poetry.pool.all_repositories:
                if (
                    not isinstance(repository, HTTPRepository)
                    or repository.url not in indexes
                ):
                    continue

                url = (
                    repository.authenticated_url
                    if self._with_credentials
                    else repository.url
                )
                parsed_url = urllib.parse.urlsplit(url)
                if parsed_url.scheme == "http":
                    indexes_header += f"--trusted-host {parsed_url.netloc}\n"
                if (
                    not has_pypi_repository
                    and repository is self._poetry.pool.repositories[0]
                ):
                    indexes_header += f"--index-url {url}\n"
                else:
                    indexes_header += f"--extra-index-url {url}\n"

            content = indexes_header + "\n" + content

        return content

    _export_constraints_txt = partialmethod(
        _export_generic_txt, with_extras=False, allow_editable=False
    )

    _export_requirements_txt = partialmethod(
        _export_generic_txt, with_extras=True, allow_editable=True
    )

    def _get_poetry_version(self) -> str:
        return metadata.version("poetry")

    def _export_pylock_toml(self, out_dir: Path) -> str:
        from tomlkit import aot
        from tomlkit import array
        from tomlkit import document
        from tomlkit import inline_table
        from tomlkit import table

        min_poetry_version = "2.3.0"
        if Version.parse(self._get_poetry_version()) < Version.parse(
            min_poetry_version
        ):
            raise RuntimeError(
                "Exporting pylock.toml requires Poetry version"
                f" {min_poetry_version} or higher."
            )

        if not self._poetry.locker.is_locked_groups_and_markers():
            raise RuntimeError(
                "Cannot export pylock.toml because the lock file is not at least version 2.1"
            )

        def add_file_info(
            archive: dict[str, Any],
            locked_file_info: PackageFile,
            additional_file_info: PackageFile | None = None,
        ) -> None:
            # We only use additional_file_info for url, upload_time and size
            # because they are not in locked_file_info.
            if additional_file_info:
                archive["name"] = locked_file_info["file"]
                url = additional_file_info.get("url")
                assert url, "url must be present in additional_file_info"
                archive["url"] = url
                if upload_time := additional_file_info.get("upload_time"):
                    with contextlib.suppress(ValueError):
                        # Python < 3.11 does not support 'Z' suffix for UTC, replace it with '+00:00'
                        archive["upload-time"] = datetime.fromisoformat(
                            upload_time.replace("Z", "+00:00")
                        )
                if size := additional_file_info.get("size"):
                    archive["size"] = size
            archive["hashes"] = dict([locked_file_info["hash"].split(":", 1)])

        python_constraint = self._poetry.package.python_constraint
        python_marker = parse_marker(
            create_nested_marker("python_version", python_constraint)
        )

        lock = document()
        lock["lock-version"] = "1.0"
        if self._poetry.package.python_versions != "*":
            lock["environments"] = [str(python_marker)]
            lock["requires-python"] = str(python_constraint)
        lock["created-by"] = "poetry-plugin-export"

        packages = aot()
        for dependency_package in get_project_dependency_packages2(
            self._poetry.locker,
            groups=set(self._groups),
            extras=self._extras,
        ):
            dependency = dependency_package.dependency
            package = dependency_package.package
            data = table()
            data["name"] = package.name
            data["version"] = str(package.version)
            if not package.marker.is_any():
                data["marker"] = str(package.marker)
            if not package.python_constraint.is_any():
                data["requires-python"] = str(package.python_constraint)
            packages.append(data)
            match dependency:
                case VCSDependency():
                    vcs = {}
                    vcs["type"] = "git"
                    vcs["url"] = dependency.source
                    vcs["requested-revision"] = dependency.reference
                    assert dependency.source_resolved_reference, (
                        "VCSDependency must have a resolved reference"
                    )
                    vcs["commit-id"] = dependency.source_resolved_reference
                    if dependency.directory:
                        vcs["subdirectory"] = dependency.directory
                    data["vcs"] = vcs
                case DirectoryDependency():
                    # The version MUST NOT be included when it cannot be guaranteed
                    # to be consistent with the code used
                    del data["version"]
                    dir_: dict[str, Any] = {}
                    try:
                        dir_["path"] = dependency.full_path.relative_to(
                            out_dir
                        ).as_posix()
                    except ValueError:
                        dir_["path"] = dependency.full_path.as_posix()
                    if package.develop:
                        dir_["editable"] = package.develop
                    data["directory"] = dir_
                case FileDependency():
                    archive = inline_table()
                    try:
                        archive["path"] = dependency.full_path.relative_to(
                            out_dir
                        ).as_posix()
                    except ValueError:
                        archive["path"] = dependency.full_path.as_posix()
                    assert len(package.files) == 1, (
                        "FileDependency must have exactly one file"
                    )
                    add_file_info(archive, package.files[0])
                    if dependency.directory:
                        archive["subdirectory"] = dependency.directory
                    data["archive"] = archive
                case URLDependency():
                    archive = inline_table()
                    archive["url"] = dependency.url
                    assert len(package.files) == 1, (
                        "URLDependency must have exactly one file"
                    )
                    add_file_info(archive, package.files[0])
                    if dependency.directory:
                        archive["subdirectory"] = dependency.directory
                    data["archive"] = archive
                case _:
                    data["index"] = package.source_url or "https://pypi.org/simple"
                    pool_info = {
                        p["file"]: p
                        for p in self._poetry.pool.package(
                            package.name,
                            package.version,
                            package.source_reference or "PyPI",
                        ).files
                    }
                    artifacts = {
                        k: list(v)
                        for k, v in itertools.groupby(
                            package.files,
                            key=(
                                lambda x: "wheel"
                                if x["file"].endswith(".whl")
                                else "sdist"
                            ),
                        )
                    }

                    sdist_files = list(artifacts.get("sdist", []))
                    for sdist in sdist_files:
                        sdist_table = inline_table()
                        data["sdist"] = sdist_table
                        add_file_info(sdist_table, sdist, pool_info[sdist["file"]])
                    if wheels := list(artifacts.get("wheel", [])):
                        wheel_array = array()
                        data["wheels"] = wheel_array
                        wheel_array.multiline(True)
                        for wheel in wheels:
                            wheel_table = inline_table()
                            add_file_info(wheel_table, wheel, pool_info[wheel["file"]])
                            wheel_array.append(wheel_table)

        lock["packages"] = packages if packages else []

        lock["tool"] = {}
        lock["tool"]["poetry-plugin-export"] = {}  # type: ignore[index]
        lock["tool"]["poetry-plugin-export"]["groups"] = sorted(  # type: ignore[index]
            self._groups, key=lambda x: (x != "main", x)
        )
        lock["tool"]["poetry-plugin-export"]["extras"] = sorted(self._extras)  # type: ignore[index]

        # Poetry writes invalid requires-python for "or" relations.
        # Though Poetry could parse it, other tools would fail.
        # Since requires-python is redundant with markers, we just comment it out.
        lock_lines = [
            f"# {line}"
            if line.startswith("requires-python = ") and "||" in line
            else line
            for line in lock.as_string().splitlines()
        ]
        return "\n".join(lock_lines) + "\n"
