# Poetry Plugin: Export

[![Poetry](https://img.shields.io/endpoint?url=https://python-poetry.org/badge/v0.json)](https://python-poetry.org/)

This package is a plugin that allows the export of locked packages to various formats.

**Note**: For now, only the `constraints.txt` and `requirements.txt` formats are available.

This plugin provides the same features as the existing `export` command of Poetry which it will eventually replace.


## Installation

The easiest way to install the `export` plugin is via the `self add` command of Poetry.

```bash
poetry self add poetry-plugin-export
```

If you used `pipx` to install Poetry you can add the plugin via the `pipx inject` command.

```bash
pipx inject poetry poetry-plugin-export
```

Otherwise, if you used `pip` to install Poetry you can add the plugin packages via the `pip install` command.

```bash
pip install poetry-plugin-export
```


## Usage

The plugin provides an `export` command to export to the desired format.

```bash
poetry export -f requirements.txt --output requirements.txt
```

**Note**: Only the `constraints.txt` and `requirements.txt` formats are currently supported.

### Available options

* `--format (-f)`: The format to export to (default: `requirements.txt`). Currently, only `constraints.txt` and `requirements.txt` are supported.
* `--output (-o)`: The name of the output file.  If omitted, print to standard output.
* `--with`: Additional dependency groups to include. The `main` group is included by default.
* `--only`: The only dependency group to include. It is possible to exclude the `main` group this way.
* `--without`: The dependency groups to ignore. (**Deprecated**)
* `--default`: Only export the main dependencies. (**Deprecated**)
* `--dev`: Include development dependencies. (**Deprecated**)
* `--extras (-E)`: Extra sets of dependencies to include.
* `--all-extras`: Include all sets of extra dependencies.
* `--all-groups`: Include all dependency groups.
* `--without-hashes`: Exclude hashes from the exported file.
* `--with-credentials`: Include credentials for extra indices.
