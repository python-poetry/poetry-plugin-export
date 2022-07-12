from __future__ import annotations

from poetry.core.semver.helpers import parse_constraint
from poetry.core.semver.version import Version
from poetry.utils._compat import metadata


is_poetry_core_1_1_0b2_compat = not parse_constraint(">1.1.0b2").allows(
    Version.parse(metadata.version("poetry-core"))  # type: ignore[no-untyped-call]
)
