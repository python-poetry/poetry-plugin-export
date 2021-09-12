from cleo.helpers import option
from poetry.console.commands.command import Command

from poetry_export_plugin.exporter import Exporter


class ExportCommand(Command):

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
        option(
            "without",
            None,
            "The dependency groups to ignore when exporting.",
            flag=False,
            multiple=True,
        ),
        option(
            "with",
            None,
            "The optional dependency groups to include when exporting.",
            flag=False,
            multiple=True,
        ),
        option("default", None, "Only export the default dependencies."),
        option(
            "only",
            None,
            "The only dependency groups to include when exporting.",
            flag=False,
            multiple=True,
        ),
        option(
            "dev",
            None,
            "Include development dependencies. (<warning>Deprecated</warning>)",
        ),
        option("without-hashes", None, "Exclude hashes from the exported file."),
        option(
            "extras",
            "E",
            "Extra sets of dependencies to include.",
            flag=False,
            multiple=True,
        ),
        option("with-credentials", None, "Include credentials for extra indices."),
    ]

    def handle(self) -> None:
        fmt = self.option("format")

        if fmt not in Exporter.ACCEPTED_FORMATS:
            raise ValueError("Invalid export format: {}".format(fmt))

        excluded_groups = []
        included_groups = []
        only_groups = []
        if self.option("dev"):
            self.line_error(
                "<warning>The --dev option is deprecated, "
                "use the `--with dev` notation instead.</warning>"
            )
            self.line_error("")
            included_groups.append("dev")

        excluded_groups.extend(
            [
                group.strip()
                for groups in self.option("without")
                for group in groups.split(",")
            ]
        )
        included_groups.extend(
            [
                group.strip()
                for groups in self.option("with")
                for group in groups.split(",")
            ]
        )
        only_groups.extend(
            [
                group.strip()
                for groups in self.option("only")
                for group in groups.split(",")
            ]
        )

        if self.option("default"):
            only_groups.append("default")

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

            self.call("lock", " ".join(options))

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
        exporter.with_groups(included_groups)
        exporter.without_groups(excluded_groups)
        exporter.only_groups(only_groups)
        exporter.with_extras(self.option("extras"))
        exporter.with_hashes(not self.option("without-hashes"))
        exporter.with_credentials(self.option("with-credentials"))
        exporter.export(fmt, self.poetry.file.parent, output or self.io)
