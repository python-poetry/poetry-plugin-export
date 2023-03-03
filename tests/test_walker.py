from __future__ import annotations

import pytest

from packaging.utils import NormalizedName
from poetry.core.packages.dependency import Dependency
from poetry.core.packages.package import Package

from poetry_plugin_export.walker import DependencyWalkerError
from poetry_plugin_export.walker import walk_dependencies


def test_walk_dependencies_multiple_versions_when_latest_is_not_compatible() -> None:
    # TODO: Support this case:
    # https://github.com/python-poetry/poetry-plugin-export/issues/183
    with pytest.raises(DependencyWalkerError):
        walk_dependencies(
            dependencies=[
                Dependency("grpcio", ">=1.42.0"),
                Dependency("grpcio", ">=1.42.0,<=1.49.1"),
                Dependency("grpcio", ">=1.47.0,<2.0dev"),
            ],
            packages_by_name={
                "grpcio": [Package("grpcio", "1.51.3"), Package("grpcio", "1.49.1")]
            },
            root_package_name=NormalizedName("package-name"),
        )
