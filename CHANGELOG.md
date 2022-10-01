# Change Log

## [1.1.0] - 2022-10-01

### Added

- Add support for exporting `constraints.txt` files ([#128](https://github.com/python-poetry/poetry-plugin-export/pull/128)).

### Fixed

- Fix an issue where a relative path passed via `-o` was not ìnterpreted relative to the current working directory ([#130](https://github.com/python-poetry/poetry-plugin-export/pull/130)).
- Fix an issue where the names of extras were not normalized according to PEP 685 ([#123](https://github.com/python-poetry/poetry-plugin-export/pull/123)).


## [1.0.7] - 2022-09-13

### Added

- Add support for multiple extras in a single flag ([#103](https://github.com/python-poetry/poetry-plugin-export/pull/103)).
- Add `homepage` and `repository` to metadata ([#113](https://github.com/python-poetry/poetry-plugin-export/pull/113)).
- Add a `poetry-export` pre-commit hook ([#85](https://github.com/python-poetry/poetry-plugin-export/pull/85)).

### Fixed

- Fix an issue where a virtual environment was created unnecessarily when running `poetry export` (requires poetry 1.2.1) ([#106](https://github.com/python-poetry/poetry-plugin-export/pull/106)).
- Fix an issue where package sources were not taken into account ([#111](https://github.com/python-poetry/poetry-plugin-export/pull/111)).
- Fix an issue where trying to export with extras that do not exist results in empty output ([#103](https://github.com/python-poetry/poetry-plugin-export/pull/103)).
- Fix an issue where exporting a dependency on a package with a non-existent extra fails ([#109](https://github.com/python-poetry/poetry-plugin-export/pull/109)).
- Fix an issue where only one of `--index-url` and `--extra-index-url` were exported ([#117](https://github.com/python-poetry/poetry-plugin-export/pull/117)).


## [1.0.6] - 2022-08-07

### Fixed

- Fixed an issue the markers of exported dependencies overlapped. [#94](https://github.com/python-poetry/poetry-plugin-export/pull/94)


## [1.0.5] - 2022-07-12

### Added

- Added LICENSE file. [#81](https://github.com/python-poetry/poetry-plugin-export/pull/81)


## [1.0.4] - 2022-05-26

### Fixed

- Fixed an issue where the exported dependencies did not list their active extras. [#65](https://github.com/python-poetry/poetry-plugin-export/pull/65)


## [1.0.3] - 2022-05-23

This release fixes test suite compatibility with upcoming Poetry releases. No functional changes.


## [1.0.2] - 2022-05-10

### Fixed

- Fixed an issue where the exported hashes were not sorted. [#54](https://github.com/python-poetry/poetry-plugin-export/pull/54)

### Changes

- The implicit dependency group was renamed from "default" to "main". (Requires poetry-core > 1.1.0a7 to take effect.) [#52](https://github.com/python-poetry/poetry-plugin-export/pull/52)


## [1.0.1] - 2022-04-11

### Fixed

- Fixed a regression where export incorrectly always exported default group only. [#50](https://github.com/python-poetry/poetry-plugin-export/pull/50)


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

- Fixed the output for packages with markers. [#13](https://github.com/python-poetry/poetry-plugin-export/pull/13)
- Check the existence of the `export` command before attempting to delete it. [#18](https://github.com/python-poetry/poetry-plugin-export/pull/18)


## [0.2.0] - 2021-09-13

### Added

- Added support for dependency groups. [#6](https://github.com/python-poetry/poetry-plugin-export/pull/6)


[Unreleased]: https://github.com/python-poetry/poetry-plugin-export/compare/1.1.0...main
[1.1.0]: https://github.com/python-poetry/poetry-plugin-export/releases/tag/1.1.0
[1.0.7]: https://github.com/python-poetry/poetry-plugin-export/releases/tag/1.0.7
[1.0.6]: https://github.com/python-poetry/poetry-plugin-export/releases/tag/1.0.6
[1.0.5]: https://github.com/python-poetry/poetry-plugin-export/releases/tag/1.0.5
[1.0.4]: https://github.com/python-poetry/poetry-plugin-export/releases/tag/1.0.4
[1.0.3]: https://github.com/python-poetry/poetry-plugin-export/releases/tag/1.0.3
[1.0.2]: https://github.com/python-poetry/poetry-plugin-export/releases/tag/1.0.2
[1.0.1]: https://github.com/python-poetry/poetry-plugin-export/releases/tag/1.0.1
[1.0.0]: https://github.com/python-poetry/poetry-plugin-export/releases/tag/1.0.0
[0.2.1]: https://github.com/python-poetry/poetry-plugin-export/releases/tag/0.2.1
[0.2.0]: https://github.com/python-poetry/poetry-plugin-export/releases/tag/0.2.0
