# Poetry Plugin: Export

[![Poetry](https://img.shields.io/endpoint?url=https://python-poetry.org/badge/v0.json)](https://python-poetry.org/)

This package is a plugin that allows the export of locked packages to various formats.

**Note**: For now, only the `constraints.txt` and `requirements.txt` formats are available.

This plugin provides the same features as the existing `export` command of Poetry which it will eventually replace.


## Installation

On Poetry 2.0 and newer, the easiest way to add the `export` plugin is to declare it as a required Poetry plugin.

```toml
[tool.poetry.requires-plugins]
poetry-plugin-export = ">=1.8"
```

Otherwise, install the plugin via the `self add` command of Poetry.

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

> [!IMPORTANT]
> When installing an exported `requirements.txt` via `pip`, you should always pass `--no-deps`
> because Poetry has already resolved the dependencies so that all direct and transitive
> requirements are included and it is not necessary to resolve again via `pip`.
> `pip` may even fail to resolve dependencies, especially if `git` dependencies,
> which are exported with their resolved hashes, are included.

> [!NOTE]
> The following formats are currently supported:
> * `requirements.txt`
> * `constraints.txt`
> * `pylock.toml`

### Available options

* `--format (-f)`: The format to export to (default: `requirements.txt`). Additionally, `constraints.txt` and `pylock.toml` are supported.
* `--output (-o)`: The name of the output file.  If omitted, print to standard output.
* `--with`: The optional and non-optional dependency groups to include. By default, only the main dependencies are included.
* `--only`: The only dependency groups to include. It is possible to exclude the `main` group this way.
* `--without`: The dependency groups to ignore. (**Deprecated**)
* `--default`: Only export the main dependencies. (**Deprecated**)
* `--dev`: Include development dependencies. (**Deprecated**)
* `--extras (-E)`: Extra sets of dependencies to include.
* `--all-extras`: Include all sets of extra dependencies.
* `--all-groups`: Include all dependency groups.
* `--without-hashes`: Exclude hashes from the exported file.
* `--with-credentials`: Include credentials for extra indices.
