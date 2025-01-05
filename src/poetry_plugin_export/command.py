from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from cleo.helpers import option
from packaging.utils import NormalizedName
from packaging.utils import canonicalize_name
from poetry.console.commands.group_command import GroupCommand
from poetry.core.packages.dependency_group import MAIN_GROUP

from poetry_plugin_export.exporter import Exporter


if TYPE_CHECKING:
    from collections.abc import Iterable


class ExportCommand(GroupCommand):
    name = "export"
    description = "Exports the lock file to alternative formats."

    options = [  # noqa: RUF012
        option(
            "format",
            "f",
            "Format to export to. Currently, only constraints.txt and"
            " requirements.txt are supported.",
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
        option("all-groups", None, "Include all dependency groups"),
        option(
            "with",
            None,
            # note: unlike poetry install, the default excludes non-optional groups
            "The optional and non-optional dependency groups to include."
            " By default, only the main dependencies are included.",
            flag=False,
            multiple=True,
        ),
        option(
            "only",
            None,
            "The only dependency groups to include.",
            flag=False,
            multiple=True,
        ),
        option(
            "without",
            None,
            # deprecated: groups are always excluded by default
            "The dependency groups to ignore. (<warning>Deprecated</warning>)",
            flag=False,
            multiple=True,
        ),
        option(
            "extras",
            "E",
            "Extra sets of dependencies to include.",
            flag=False,
            multiple=True,
        ),
        option("all-extras", None, "Include all sets of extra dependencies."),
        option("with-credentials", None, "Include credentials for extra indices."),
    ]

    @property
    def default_groups(self) -> set[str]:
        return {MAIN_GROUP}

    def handle(self) -> int:
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
                "<error>"
                "pyproject.toml changed significantly since poetry.lock was last"
                " generated. Run `poetry lock` to fix the lock file."
                "</error>"
            )
            return 1

        if self.option("extras") and self.option("all-extras"):
            self.line_error(
                "<error>You cannot specify explicit"
                " `<fg=yellow;options=bold>--extras</>` while exporting"
                " using `<fg=yellow;options=bold>--all-extras</>`.</error>"
            )
            return 1

        extras: Iterable[NormalizedName]
        if self.option("all-extras"):
            extras = self.poetry.package.extras.keys()
        else:
            extras = {
                canonicalize_name(extra)
                for extra_opt in self.option("extras")
                for extra in extra_opt.split()
            }
            invalid_extras = extras - self.poetry.package.extras.keys()
            if invalid_extras:
                raise ValueError(
                    f"Extra [{', '.join(sorted(invalid_extras))}] is not specified."
                )

        if (
            self.option("with") or self.option("without") or self.option("only")
        ) and self.option("all-groups"):
            self.line_error(
                "<error>You cannot specify explicit"
                " `<fg=yellow;options=bold>--with</>`, "
                "`<fg=yellow;options=bold>--without</>`, "
                "or `<fg=yellow;options=bold>--only</>` "
                "while exporting using `<fg=yellow;options=bold>--all-groups</>`.</error>"
            )
            return 1

        groups = (
            self.poetry.package.dependency_group_names(include_optional=True)
            if self.option("all-groups")
            else self.activated_groups
        )

        exporter = Exporter(self.poetry, self.io)
        exporter.only_groups(list(groups))
        exporter.with_extras(list(extras))
        exporter.with_hashes(not self.option("without-hashes"))
        exporter.with_credentials(self.option("with-credentials"))
        exporter.with_urls(not self.option("without-urls"))
        exporter.export(fmt, Path.cwd(), output or self.io)

        return 0
