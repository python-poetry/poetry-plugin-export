# Poetry export plugin

This package is a fork of [poetry/poetry-export-plugin](https://github.com/tailify/poetry-export-plugin) plugin
that allows the export of locked packages with packages matching a regexp excluded from the output. The functionality
frequently required to build Docker images or in monorepo builds.

## Installation

The easiest way to install the `export` plugin is via the `plugin add` command of Poetry.

```bash
poetry plugin add poetry-export-plugin
```

If you used `pipx` to install Poetry you can add the plugin via the `pipx inject` command.

```bash
pipx inject poetry poetry-export-plugin
```

Otherwise, if you used `pip` to install Poetry you can add the plugin packages via the `pip install` command.

```bash
pip install poetry-export-plugin
```


## Usage

The plugin provides an `export` command to export to the desired format.

```bash
poetry export -f requirements.txt --output requirements.txt
```

**Note**: Only the `requirements.txt` format is currently supported.

### Available options

* `--format (-f)`: The format to export to (default: `requirements.txt`). Currently, only `requirements.txt` is supported.
* `--output (-o)`: The name of the output file.  If omitted, print to standard output.
* `--without`: The dependency groups to ignore when exporting.
* `--with`: The optional dependency groups to include when exporting.
* `--only`: The only dependency groups to include when exporting.
* `--default`: Only export the default dependencies.
* `--dev`: Include development dependencies. (**Deprecated**)
* `--extras (-E)`: Extra sets of dependencies to include.
* `--without-hashes`: Exclude hashes from the exported file.
* `--with-credentials`: Include credentials for extra indices.
