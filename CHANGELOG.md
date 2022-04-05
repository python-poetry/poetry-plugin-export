# Change Log

## [1.0.0] - 2022-04-05

### Fixed

- Fixed an issue with dependency selection when duplicates exist with different markers. [poetry#4932](https://github.com/python-poetry/poetry/pull/4932)
- Fixed an issue where unconstrained duplicate dependencies are listed with conditional on python version. [poetry#5141](https://github.com/python-poetry/poetry/issues/5141)

### Changes

- Export command now constraints all exported dependencies with the root project's python version constraint. [poetry#5156](https://github.com/python-poetry/poetry/pull/5156)

### Added

- Added support for `--without-urls` option. [poetry#4763](https://github.com/python-poetry/poetry/pull/4763)


## [0.2.1] - 2021-11-24

### Fixed

- Fixed the output for packages with markers. [#13](https://github.com/python-poetry/poetry-export-plugin/pull/13)
- Check the existence of the `export` command before attempting to delete it. [#18](https://github.com/python-poetry/poetry-export-plugin/pull/18)


## [0.2.0] - 2021-09-13

### Added

- Added support for dependency groups. [#6](https://github.com/python-poetry/poetry-export-plugin/pull/6)


[Unreleased]: https://github.com/python-poetry/poetry/compare/0.2.1...main
[0.2.1]: https://github.com/python-poetry/poetry/compare/0.2.1
[0.2.0]: https://github.com/python-poetry/poetry/compare/0.2.0
