from __future__ import annotations

import os

from contextlib import contextmanager
from typing import TYPE_CHECKING
from typing import Any
from typing import Iterator

from poetry.console.application import Application
from poetry.factory import Factory
from poetry.installation.executor import Executor
from poetry.packages import Locker


if TYPE_CHECKING:
    from pathlib import Path

    from poetry.core.packages.package import Package
    from poetry.installation.operations.operation import Operation
    from poetry.poetry import Poetry
    from tomlkit.toml_document import TOMLDocument


class PoetryTestApplication(Application):
    def __init__(self, poetry: Poetry) -> None:
        super().__init__()
        self._poetry = poetry

    def reset_poetry(self) -> None:
        poetry = self._poetry
        assert poetry
        self._poetry = Factory().create_poetry(poetry.file.path.parent)
        self._poetry.set_pool(poetry.pool)
        self._poetry.set_config(poetry.config)
        self._poetry.set_locker(
            TestLocker(poetry.locker.lock, self._poetry.local_config)
        )


class TestLocker(Locker):
    def __init__(self, lock: str | Path, local_config: dict[str, Any]) -> None:
        super().__init__(lock, local_config)
        self._locked = False
        self._write = False
        self._contains_credential = False

    def write(self, write: bool = True) -> None:
        self._write = write

    def is_locked(self) -> bool:
        return self._locked

    def locked(self, is_locked: bool = True) -> TestLocker:
        self._locked = is_locked

        return self

    def mock_lock_data(self, data: dict[str, Any]) -> None:
        self.locked()

        self._lock_data = data

    def is_fresh(self) -> bool:
        return True

    def _write_lock_data(self, data: TOMLDocument) -> None:
        if self._write:
            super()._write_lock_data(data)
            self._locked = True
            return

        self._lock_data = data


class TestExecutor(Executor):
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)

        self._installs: list[Package] = []
        self._updates: list[Package] = []
        self._uninstalls: list[Package] = []

    @property
    def installations(self) -> list[Package]:
        return self._installs

    @property
    def updates(self) -> list[Package]:
        return self._updates

    @property
    def removals(self) -> list[Package]:
        return self._uninstalls

    def _do_execute_operation(self, operation: Operation) -> int:
        super()._do_execute_operation(operation)

        if not operation.skipped:
            getattr(self, f"_{operation.job_type}s").append(operation.package)

        return 0

    def _execute_install(self, operation: Operation) -> int:
        return 0

    def _execute_update(self, operation: Operation) -> int:
        return 0

    def _execute_remove(self, operation: Operation) -> int:
        return 0


@contextmanager
def as_cwd(path: Path) -> Iterator[Path]:
    old_cwd = os.getcwd()
    os.chdir(path)
    try:
        yield path
    finally:
        os.chdir(old_cwd)
