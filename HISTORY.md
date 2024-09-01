# History

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