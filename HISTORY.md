# History

## [1.1.0] - 15/03/2026

### Added
- `App.evaluate()`: evaluate Qlik expressions and master measures with optional filters; supports `evaluate` (read-only, via EvaluateEx / session hypercube with qContextSetExpression) and `selections` (via field selections) methods
- `App.clear_selections()`: clears all current selections in the app
- `App.select_values()`: selects values in a field for manual selection management
- `Object.get_data()`: fetches hypercube data from a chart or table and returns it as a pandas DataFrame with automatic pagination
- `qsea.setup_logging()`: public API for configuring library logging (file or console output); NullHandler attached by default so log output is suppressed until explicitly enabled

### Changed
- Packaging migrated from `setup.py` to `pyproject.toml` with `setuptools.build_meta` backend
- `_to_qlik()` now uses `json.dumps()` for proper string escaping
- Maintainer workflow switched to `uv build` / `uv sync`

### Fixed
- Logging configuration: level parameter corrected (`logging.INFO` instead of `logging.info`)
- Improved websocket connection error handling

## [0.0.24] - 2024-09-28
- Object.copy() function now can copy complex objects such as filterpanes and containers.

## [0.0.23] - 2024-09-15
- Fixed a bug in the sheet.copy function that sometimes caused objects to be duplicated on the target sheet

## [0.0.22] - 2024-09-02
- Minor changes

## [0.0.21] - 2024-09-01
- Added sheet.copy and object.copy functions, now sheets and objects can be easily copied to another apps
- Added measure.copy and dimension.copy functions, makes the syntax clearer
- load function now can be rerun without recreating the app object
- measures.add, dimensions.add and variables.add now return the ID of the object created (None if failed)
- Added sheets.add function, which creates a new sheet in the app
- Added sheet.clear function, which clears all objects from a sheet

## [0.0.20] - 2024-08-26
- Fixed minor bugs

## [0.0.19] - 2024-08-25
- Added bookmark support
- Added support for measure and dimension base colors
- Added 'source' parameter to 'add' function to copy the measure or dimension from another app 
- Fixed an error proceeding an empty sheet
- Fixed minor bugs

## [0.0.17] - 2024-01-31
- Fixed some problems that occured if the connection class object was recreated before terminating the connection to Qlik Sense Engine API

## [0.0.16] - 2023-10-03
- Minor changes

## [0.0.15] - 2023-10-03
- Minor changes

## [0.0.14] - 2023-10-01

### Added
- object.export_data() function which performs data export of an object (such as a table or chart) to an xslx or csv file
- get_layout() function for measures, dimensions, variables, sheets and objects; the functions return the json layout