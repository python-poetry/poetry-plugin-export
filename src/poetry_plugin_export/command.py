from __future__ import annotations

from cleo.helpers import option
from poetry.console.commands.installer_command import InstallerCommand


try:
    from poetry.core.packages.dependency_group import MAIN_GROUP
except ImportError:
    MAIN_GROUP = "default"

from poetry_plugin_export.exporter import Exporter


class ExportCommand(InstallerCommand):
    name = "export"
    description = "Exports the lock file to alternative formats."

    options = [
        option(
            "format",
            "f",
            "Format to export to. Currently, only requirements.txt is supported.",
            flag=False,
            default=Exporter.FORMAT_REQUIREMENTS_TXT,
        ),
        option("output", "o", "The name of the output file.", flag=False),
        option("without-hashes", None, "Exclude hashes from the exported file."),
        option(
            "without-urls",
            None,
            "Exclude source repository urls from the exported file.",
        ),
        option(
            "dev",
            None,
            "Include development dependencies. (<warning>Deprecated</warning>)",
        ),
        *InstallerCommand._group_dependency_options(),
        option(
            "extras",
            "E",
            "Extra sets of dependencies to include.",
            flag=False,
            multiple=True,
        ),
        option("with-credentials", None, "Include credentials for extra indices."),
    ]

    @property
    def non_optional_groups(self) -> set[str]:
        # method only required for poetry <= 1.2.0-beta.2.dev0
        return {MAIN_GROUP}

    @property
    def default_groups(self) -> set[str]:
        return {MAIN_GROUP}

    def handle(self) -> None:
        fmt = self.option("format")

        if not Exporter.is_format_supported(fmt):
            raise ValueError(f"Invalid export format: {fmt}")

        output = self.option("output")

        locker = self.poetry.locker
        if not locker.is_locked():
            self.line_error("<comment>The lock file does not exist. Locking.</comment>")
            options = []
            if self.io.is_debug():
                options.append(("-vvv", None))
            elif self.io.is_very_verbose():
                options.append(("-vv", None))
            elif self.io.is_verbose():
                options.append(("-v", None))

            self.call("lock", " ".join(options))  # type: ignore[arg-type]

        if not locker.is_fresh():
            self.line_error(
                "<warning>"
                "Warning: The lock file is not up to date with "
                "the latest changes in pyproject.toml. "
                "You may be getting outdated dependencies. "
                "Run update to update them."
                "</warning>"
            )

        exporter = Exporter(self.poetry)
        exporter.only_groups(list(self.activated_groups))
        exporter.with_extras(self.option("extras"))
        exporter.with_hashes(not self.option("without-hashes"))
        exporter.with_credentials(self.option("with-credentials"))
        exporter.with_urls(not self.option("without-urls"))
        exporter.export(fmt, self.poetry.file.parent, output or self.io)
