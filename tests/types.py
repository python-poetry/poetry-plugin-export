from __future__ import annotations

from typing import TYPE_CHECKING
from typing import Protocol  # noqa: TYP001


if TYPE_CHECKING:
    from cleo.testers.command_tester import CommandTester
    from poetry.installation import Installer
    from poetry.installation.executor import Executor
    from poetry.poetry import Poetry
    from poetry.utils.env import Env


class CommandTesterFactory(Protocol):
    def __call__(
        self,
        command: str,
        poetry: Poetry | None = None,
        installer: Installer | None = None,
        executor: Executor | None = None,
        environment: Env | None = None,
    ) -> CommandTester:
        ...


class ProjectFactory(Protocol):
    def __call__(
        self,
        name: str,
        dependencies: dict[str, str] | None = None,
        dev_dependencies: dict[str, str] | None = None,
        pyproject_content: str | None = None,
        poetry_lock_content: str | None = None,
        install_deps: bool = True,
    ) -> Poetry:
        ...
