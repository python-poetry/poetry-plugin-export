from __future__ import annotations

from poetry.core.version.markers import parse_marker


MARKER_WIN32 = parse_marker('sys_platform == "win32"')
MARKER_WINDOWS = parse_marker('platform_system == "Windows"')
MARKER_LINUX = parse_marker('sys_platform == "linux"')
MARKER_DARWIN = parse_marker('sys_platform == "darwin"')

MARKER_CPYTHON = parse_marker('implementation_name == "cpython"')

MARKER_PY27 = parse_marker('python_version >= "2.7" and python_version < "2.8"')

MARKER_PY36 = parse_marker('python_version >= "3.6" and python_version < "4.0"')
MARKER_PY36_38 = parse_marker('python_version >= "3.6" and python_version < "3.8"')
MARKER_PY36_PY362 = parse_marker(
    'python_version >= "3.6" and python_full_version < "3.6.2"'
)
MARKER_PY362_PY40 = parse_marker(
    'python_full_version >= "3.6.2" and python_version < "4.0"'
)
MARKER_PY36_ONLY = parse_marker('python_version >= "3.6" and python_version < "3.7"')

MARKER_PY37 = parse_marker('python_version >= "3.7" and python_version < "4.0"')

MARKER_PY = MARKER_PY27.union(MARKER_PY36)

MARKER_PY_WIN32 = MARKER_PY.intersect(MARKER_WIN32)
MARKER_PY_WINDOWS = MARKER_PY.intersect(MARKER_WINDOWS)
MARKER_PY_LINUX = MARKER_PY.intersect(MARKER_LINUX)
MARKER_PY_DARWIN = MARKER_PY.intersect(MARKER_DARWIN)
