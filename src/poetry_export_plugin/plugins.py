from importlib import import_module
from typing import TYPE_CHECKING
from typing import Callable
from typing import Type

from poetry.plugins.application_plugin import ApplicationPlugin


if TYPE_CHECKING:
    from poetry.console.application import Application
    from poetry.console.commands.command import Command


def load_command(name: str) -> Callable:
    def _load() -> Type["Command"]:
        module = import_module(
            "poetry_export_plugin.console.commands.{}".format(".".join(name.split(" ")))
        )
        command_class = getattr(
            module, "{}Command".format("".join(c.title() for c in name.split(" ")))
        )

        return command_class()

    return _load


COMMANDS = ["export"]


class ExportApplicationPlugin(ApplicationPlugin):
    def activate(self, application: "Application"):
        # Removing the existing export command to avoid an error
        # until Poetry removes the export command
        # and uses this plugin instead.

        # If you're checking this code out to get inspiration
        # for your own plugins: DON'T DO THIS!
        if "export" in application.command_loader._factories:
            del application.command_loader._factories["export"]

        for command in COMMANDS:
            application.command_loader.register_factory(command, load_command(command))
