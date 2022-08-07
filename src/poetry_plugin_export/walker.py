from __future__ import annotations

from copy import deepcopy
from typing import TYPE_CHECKING

from poetry.packages import DependencyPackage
from poetry.utils.extras import get_extra_package_names


if TYPE_CHECKING:
    from collections.abc import Iterable
    from collections.abc import Iterator
    from collections.abc import Sequence

    from poetry.core.packages.dependency import Dependency
    from poetry.core.packages.package import Package
    from poetry.core.version.markers import BaseMarker
    from poetry.packages import Locker


def get_project_dependency_packages(
    locker: Locker,
    project_requires: list[Dependency],
    project_python_marker: BaseMarker | None = None,
    extras: bool | Sequence[str] | None = None,
) -> Iterator[DependencyPackage]:
    # Apply the project python marker to all requirements.
    if project_python_marker is not None:
        marked_requires: list[Dependency] = []
        for require in project_requires:
            require = deepcopy(require)
            require.marker = require.marker.intersect(project_python_marker)
            marked_requires.append(require)
        project_requires = marked_requires

    repository = locker.locked_repository()

    # Build a set of all packages required by our selected extras
    extra_package_names: set[str] | None = None

    if extras is not True:
        extra_package_names = set(
            get_extra_package_names(
                repository.packages,
                locker.lock_data.get("extras", {}),
                extras or (),
            )
        )

    # If a package is optional and we haven't opted in to it, do not select
    selected = []
    for dependency in project_requires:
        try:
            package = repository.find_packages(dependency=dependency)[0]
        except IndexError:
            continue

        if extra_package_names is not None and (
            package.optional and package.name not in extra_package_names
        ):
            # a package is locked as optional, but is not activated via extras
            continue

        selected.append(dependency)

    for package, dependency in get_project_dependencies(
        project_requires=selected,
        locked_packages=repository.packages,
    ):
        yield DependencyPackage(dependency=dependency, package=package)


def get_project_dependencies(
    project_requires: list[Dependency],
    locked_packages: list[Package],
) -> Iterable[tuple[Package, Dependency]]:
    # group packages entries by name, this is required because requirement might use
    # different constraints.
    packages_by_name: dict[str, list[Package]] = {}
    for pkg in locked_packages:
        if pkg.name not in packages_by_name:
            packages_by_name[pkg.name] = []
        packages_by_name[pkg.name].append(pkg)

    # Put higher versions first so that we prefer them.
    for packages in packages_by_name.values():
        packages.sort(
            key=lambda package: package.version,
            reverse=True,
        )

    nested_dependencies = walk_dependencies(
        dependencies=project_requires,
        packages_by_name=packages_by_name,
    )

    return nested_dependencies.items()


def walk_dependencies(
    dependencies: list[Dependency],
    packages_by_name: dict[str, list[Package]],
) -> dict[Package, Dependency]:
    nested_dependencies: dict[Package, Dependency] = {}

    visited: set[tuple[Dependency, BaseMarker]] = set()
    while dependencies:
        requirement = dependencies.pop(0)
        if (requirement, requirement.marker) in visited:
            continue
        visited.add((requirement, requirement.marker))

        locked_package = get_locked_package(
            requirement, packages_by_name, nested_dependencies
        )

        if not locked_package:
            raise RuntimeError(f"Dependency walk failed at {requirement}")

        if requirement.extras:
            locked_package = locked_package.with_features(requirement.extras)

        # create dependency from locked package to retain dependency metadata
        # if this is not done, we can end-up with incorrect nested dependencies
        constraint = requirement.constraint
        marker = requirement.marker
        requirement = locked_package.to_dependency()
        requirement.marker = requirement.marker.intersect(marker)

        requirement.constraint = constraint

        for require in locked_package.requires:
            if require.is_optional() and not any(
                require in locked_package.extras[feature]
                for feature in locked_package.features
            ):
                continue

            require = deepcopy(require)
            require.marker = require.marker.intersect(
                requirement.marker.without_extras()
            )
            if not require.marker.is_empty():
                dependencies.append(require)

        key = locked_package
        if key not in nested_dependencies:
            nested_dependencies[key] = requirement
        else:
            nested_dependencies[key].marker = nested_dependencies[key].marker.union(
                requirement.marker
            )

    return nested_dependencies


def get_locked_package(
    dependency: Dependency,
    packages_by_name: dict[str, list[Package]],
    decided: dict[Package, Dependency] | None = None,
) -> Package | None:
    """
    Internal helper to identify corresponding locked package using dependency
    version constraints.
    """
    decided = decided or {}

    # Get the packages that are consistent with this dependency.
    packages = [
        package
        for package in packages_by_name.get(dependency.name, [])
        if package.python_constraint.allows_all(dependency.python_constraint)
        and dependency.constraint.allows(package.version)
    ]

    # If we've previously made a choice that is compatible with the current
    # requirement, stick with it.
    for package in packages:
        old_decision = decided.get(package)
        if (
            old_decision is not None
            and not old_decision.marker.intersect(dependency.marker).is_empty()
        ):
            return package

    return next(iter(packages), None)
