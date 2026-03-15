from __future__ import annotations

import datetime as dt
from typing import List, Union, TYPE_CHECKING

import pandas as pd

from qsea._config import logger
from qsea._engine import query, _get_properties, _set_properties, _get_layout, _next_rpc_id
from qsea._helpers import _to_qlik
from qsea._loaders import _get_hypercube_data

if TYPE_CHECKING:
    from qsea.app import App


class Variable:
    """
    The class, representing the variables of the application
    Member of the App.variables collection
    """

    def __init__(self, parent, varName):
        self.name = varName
        
        self.parent = parent
        self.ws = parent.ws
        self.app_handle = parent.app_handle
        self.handle = 0

        self.id = ''
        self.definition = ''
        self.description = ''
        self.created_date = dt.datetime(year=1901, month=1, day=1)
        self.modified_date = dt.datetime(year=1901, month=1, day=1)
        self.script_created = ''

    def __repr__(self):
        return f"Variable(name={self.name!r}, id={self.id!r})"

    @staticmethod
    def _from_layout(parent, layout: dict) -> 'Variable':
        """Create a Variable from a raw Engine API GetLayout response."""
        name = layout.get('qName', '')
        var = Variable(parent, name)
        var.app_handle = parent.app_handle
        var.id = layout.get('qInfo', {}).get('qId', '')
        var.definition = layout.get('qDefinition', '')
        var.description = layout.get('qComment', '')
        var.script_created = layout.get('qIsScriptCreated', False)
        if pd.isna(var.script_created):
            var.script_created = False
        return var

    def get_handle(self) -> int:
        """
        Gets the handle of the variable
        """
        logger.debug('Variable.get_handle function started, %s', self.name)
        result = query(self.parent.ws, {
          "jsonrpc": "2.0",
          "id": _next_rpc_id(),
          "method": "GetVariableById",
          "handle": self.app_handle,
          "params": [self.id]
        })
        if result is None or 'result' not in result:
            logger.error('Variable.get_handle failed for %s', self.name)
            return None
        self.handle = result['result']['qReturn']['qHandle']
        logger.debug('Variable.get_handle function completed, %s', self.handle)
        return self.handle
    
    def update(self, definition = None, description = None) -> bool:
        """
        Updates the variable on the Qlik Sense Server

        Args:
            definition (str): new definition of the variable (leave None to keep the old value)
            description (str): new description of the variable (leave None to keep the old value)

        Returns:
            True if the variable was updated successfully, False otherwise
        """
        logger.debug('Variable.update function started, name = %s, definition = %s, description = %s', self.name, definition, description)
        self.get_handle()

        # changing only nonempty values
        if definition is None:
            if pd.isna(self.definition): definition = None
            else: definition = str(self.definition)
        if description is None:
            if pd.isna(self.description): description = None
            else: description = str(self.description)
        
        query_result = query(self.ws, {
          "jsonrpc": "2.0",
          "id": _next_rpc_id(),
          "method": "ApplyPatches",
          "handle": self.handle,
          "params": [
            [
              {
                "qPath": "/qDefinition",
                "qOp": "replace",
                "qValue": _to_qlik(definition)
              },
              {
                "qPath": "/qComment",
                "qOp": "replace",
                "qValue": _to_qlik(description)
              }
            ]
          ]
        })
        
        # if success, changes the properties of a variable object
        try:
            logger.debug('Updating variable properties: %s', self.name)
            if len(query_result['change']) > 0:
                self.definition = definition
                self.description = description
                self.parent.df.loc[self.parent.df['qInfo.qId'] == self.id, 'qDefinition'] = definition
                self.parent.df.loc[self.parent.df['qInfo.qId'] == self.id, 'description'] = description
                logger.info('Variable properties updated: %s, new definition: %s, new description: %s', self.name, definition, description)
                return True
        except Exception as E:
            logger.exception('Variable.update function completed with error, name = %s, error = %s', self.name, str(E))
            return False

        logger.error('Variable.update function completed unsuccesfully, name = %s', self.name)
        return False
    
    def delete(self) -> bool:
        logger.debug('Variable.delete function started, name = %s', self.name)
        destroy_result = query(self.parent.ws, {
              "jsonrpc": "2.0",
              "id": _next_rpc_id(),
              "method": "DestroyVariableById",
              "handle": self.app_handle,
              "params": [
                self.id
              ]
            })
        
        logger.debug('Deleting variable from variables collection: %s', self.name)
        if destroy_result['result']['qSuccess']:
            logger.info('Variable deleted: %s', self.name)
            if self.script_created:
                logger.warning('Deleting the script-generated variable will not affect the state of the app after data reload: %s', self.name)
            del self.parent[self.name]
            self.parent.df = self.parent.df[self.parent.df['qInfo.qId'] != self.id]
            return True
        else: 
            logger.error('Failed to delete variable: %s', self.name)
            return False
        
    def rename(self, new_name: str) -> bool:
        #since there is no explicit method to rename a variable in Qlik Sense, we'll just create a new one and delete an old one
        logger.debug('Variable.rename function started, name = %s, new_name = %s', self.name, new_name)
        parent = self.parent
        tdef = self.definition
        tdesc = self.description
        old_name = self.name
        if pd.isna(tdesc): tdesc = ''

        add_success = parent.add(new_name, tdef, tdesc)
        if add_success:
            delete_success = self.delete()
            if delete_success:
                logger.info('Variable renamed, old_name = %s, new_name = %s', old_name, new_name)
                return True
            else:
                logger.error('Failed to delete old variable after renaming, old_name = %s, new_name = %s', old_name, new_name)
                return False
        else:
            logger.error('Failed to add new variable for renaming, old_name = %s, new_name = %s', old_name, new_name)
            return False
        
    def get_layout(self) -> dict:
        """
        Returns the layout of the variable
        """
        logger.debug('Variable.get_layout function started, %s', self.name)
        self.get_handle()
        return _get_layout(self.parent.ws, self.handle)


class Field:
    """
    The class, representing the fields of the application
    Member of the App.fields collection
    """
    def __init__(self, fieldName):
        self.name = fieldName
        self.handle = 0
        self.app_handle = 0
        
        self.table_name = ''
        self.information_density, self.non_nulls, self.rows_count, self.subset_ratio = 0, 0, 0, 0
        self.distinct_values_count, self.present_distinct_values = 0, 0
        self.key_type, self.tags = '', ''


class Measure:
    """
    The class, representing the master measures of the application
    Member of the App.measures collection
    """
    def __init__(self, parent, msName):
        self.name = msName

        self.parent = parent
        self.ws = parent.ws
        self.app_handle = parent.app_handle
        self.handle = 0
        
        self.id, self.definition, self.description, self.label, self.label_expression = '', '', '', '', ''
        self.format_type, self.format_ndec, self.format_use_thou, self.format_dec, self.format_thou = '', -1, -1, '', ''
        self.created_date, self.modified_date = dt.datetime(year=1901, month=1, day=1), dt.datetime(year=1901, month=1, day=1)
        self.base_color = ''

    def __repr__(self):
        return f"Measure(name={self.name!r}, id={self.id!r})"

    @staticmethod
    def _from_properties(parent, props: dict) -> 'Measure':
        """Create a Measure from a raw Engine API GetProperties response (qProp)."""
        title = props.get('qMetaDef', {}).get('title', '')
        ms = Measure(parent, title)
        ms.app_handle = parent.app_handle
        ms.id = props.get('qInfo', {}).get('qId', '')
        qm = props.get('qMeasure', {})
        ms.definition = qm.get('qDef', '')
        ms.label = qm.get('qLabel', '')
        ms.label_expression = qm.get('qLabelExpression', '')
        ms.description = props.get('qMetaDef', {}).get('description', '')
        nf = qm.get('qNumFormat', {})
        ms.format_type = nf.get('qType', '')
        ms.format_ndec = nf.get('qnDec', -1)
        ms.format_use_thou = nf.get('qUseThou', -1)
        ms.format_dec = nf.get('qDec', '')
        ms.format_thou = nf.get('qThou', '')
        coloring = qm.get('coloring', {})
        ms.base_color = coloring.get('baseColor', {}).get('color', '')
        return ms

    def get_handle(self) -> int:
        """
        Gets the handle of the measure
        """
        logger.debug('Measure.get_handle function started, %s', self.name)
        result = query(self.parent.ws, {
          "jsonrpc": "2.0",
          "id": _next_rpc_id(),
          "method": "GetMeasure",
          "handle": self.app_handle,
          "params": [self.id]
        })
        if result is None or 'result' not in result:
            logger.error('Measure.get_handle failed for %s', self.name)
            return None
        self.handle = result['result']['qReturn']['qHandle']
        logger.debug('Measure.get_handle function completed, %s', self.handle)
        return self.handle
    
    def update(self, definition = None, label = None, label_expression = None, description = None, format_type = None, \
               format_ndec = -1, format_use_thou = -1, format_dec = None, format_thou = None, base_color = None) -> bool:
        """
        Updates the measure properties

        Parameters
        ----------
        definition : str, optional
            The definition of the measure
        label : str, optional
            The label of the measure
        label_expression : str, optional 
            The label expression of the measure
        description : str, optional
            The description of the measure
        format_type : str, optional
            The format type of the measure
                'U' for auto
                'F' for number
                'M' for money
                'D' for date
                'IV' for duration
                'R' for other
        format_ndec : int, optional
            The number of decimals of the measure
        format_use_thou : int, optional
            The use thousands flag of the measure
        format_dec : str, optional
            The decimal separator of the measure
        format_thou : str, optional
            The thousand separator of the measure
        base_color : str, optional
            The base color of the measure (hex)

        Returns
        -------
        bool
            True if the measure was updated successfully, False otherwise
        """

        logger.debug('Measure.update function started, name = %s, definition = %s, label = %s, label_expression = %s, format_type = %s, \
                     format_ndec = %s, format_use_thou = %s, format_dec = %s, format_thou = %s', \
                        self.name, definition, label, label_expression, format_type, format_ndec, format_use_thou, format_dec, format_thou)  
        self.get_handle()

        # check if old values exist; leave old values if new values are empty
        def gn(x, y):
            if y is None or y != y:
                if pd.isna(x): return ''
                else: return str(x)
            elif isinstance(y, str):
                return str(y)
            elif y == -1: 
                if pd.isna(x): return 0
                else: return int(x)
            else: return int(y)
            
        definition, label, label_expression, description, format_type, format_ndec, format_use_thou, \
            format_dec, format_thou, base_color = \
                                    gn(self.definition, definition),           \
                                    gn(self.label, label),                     \
                                    gn(self.label_expression, label_expression), \
                                    gn(self.description, description),         \
                                    gn(self.format_type, format_type),           \
                                    gn(self.format_ndec, format_ndec),           \
                                    gn(self.format_use_thou, format_use_thou),     \
                                    gn(self.format_dec, format_dec),             \
                                    gn(self.format_thou, format_thou),           \
                                    gn(self.base_color, base_color)
        
        t = {
          "jsonrpc": "2.0",
          "id": _next_rpc_id(),
          "method": "SetProperties",
          "handle": self.handle,
          "params": [
            {
              "qInfo": {
                "qId": self.id,
                "qType": "measure"
              },
              "qMeasure": {
                  "qLabel": label,
                  "qDef": definition,
                  "qExpressions": [],
                  "qActiveExpression": 0,
                  "qLabelExpression": label_expression,
                  "qNumFormat": {
                    "qType": format_type,
                    "qnDec": format_ndec,
                    "qUseThou": format_use_thou,
                    "qFmt": "#\xa0##0",
                    "qDec": format_dec,
                    "qThou": format_thou
                  },
                  "coloring": {'baseColor': {'color': base_color, 'index': -1}}
                },
                "qMetaDef": {"title": self.name,
                            "description": description}
            }
          ]
        }
        query_result = query(self.parent.ws, t)
        
        try:
            if len(query_result['change']) > 0:
                self.definition = definition
                self.label = label
                self.label_expression = label_expression
                self.description = description
                self.format_type = format_type
                self.format_ndec = format_ndec
                self.format_use_thou = format_use_thou
                self.format_dec = format_dec
                self.format_thou = format_thou
                self.base_color = base_color
                self.parent.df.loc[self.parent.df['qInfo.qId'] == self.id, 'qData.measure.qDef'] = definition
                self.parent.df.loc[self.parent.df['qInfo.qId'] == self.id, 'qData.measure.qLabel'] = label
                self.parent.df.loc[self.parent.df['qInfo.qId'] == self.id, 'qData.measure.qLabelExpression'] = label_expression
                self.parent.df.loc[self.parent.df['qInfo.qId'] == self.id, 'qMeta.description'] = description
                self.parent.df.loc[self.parent.df['qInfo.qId'] == self.id, 'qData.measure.qNumFormat.qType'] = format_type
                self.parent.df.loc[self.parent.df['qInfo.qId'] == self.id, 'qData.measure.qNumFormat.qnDec'] = format_ndec
                self.parent.df.loc[self.parent.df['qInfo.qId'] == self.id, 'qData.measure.qNumFormat.qUseThou'] = format_use_thou
                self.parent.df.loc[self.parent.df['qInfo.qId'] == self.id, 'qData.measure.qNumFormat.qDec'] = format_dec
                self.parent.df.loc[self.parent.df['qInfo.qId'] == self.id, 'qData.measure.qNumFormat.qThou'] = format_thou
                self.parent.df.loc[self.parent.df['qInfo.qId'] == self.id, 'qData.measure.coloring.baseColor.color'] = base_color
                logger.info('Measure updated: %s, new definition: %s, new label: %s', self.name, self.definition, self.label)
                return True
        except Exception as E:
            logger.exception('Failed to update measure: %s, Error: %s', self.name, str(E))
            return False
        
        return False
    
    def delete(self) -> bool:
        """
        Delete the measure

        Returns
            True if the measure was deleted successfully, False otherwise
        """

        logger.debug('Measure.delete function started, name = %s', self.name)
        destroy_result = query(self.parent.ws, {
              "jsonrpc": "2.0",
              "id": _next_rpc_id(),
              "method": "DestroyMeasure",
              "handle": self.app_handle,
              "params": [
                self.id
              ]
            })
        
        if destroy_result['result']['qSuccess']:
            logger.info ('Measure deleted: %s', self.name)
            del self.parent[self.name]
            self.parent.df = self.parent.df[self.parent.df['qInfo.qId'] != self.id]
            return True
        else: 
            logger.error('Failed to delete measure: %s', self.name)
            return False
        
    
    def rename(self, new_name: str) -> bool:
        """
        Rename the measure

        Args: 
            new_name (str): New name of the measure

        Returns:    
            True if the measure was renamed successfully, False otherwise
        """

        logger.debug('Measure.rename function started, old_name = %s,  new_name = %s', self.name, new_name)
        self.get_handle()
        old_name = self.name

        t = {
          "jsonrpc": "2.0",
          "id": _next_rpc_id(),
          "method": "SetProperties",
          "handle": self.handle,
          "params": [
            {
              "qInfo": {
                "qId": self.id,
                "qType": "measure"
              },
                "qMetaDef": {'title': new_name}
            }
          ]
        }
        query_result = query(self.parent.ws, t)
        
        if 'change' in query_result:
            self.name = new_name
            self.parent.df.loc[self.parent.df['qInfo.qId'] == self.id, 'qMeta.title'] = new_name
            self.parent[new_name] = self.parent[old_name]
            del self.parent[old_name]
            logger.info('Measure renamed, old_name = %s, new_name = %s', old_name, new_name)
            return True
        else:
            logger.error('Failed to rename measure, old_name = %s, new_name = %s', old_name, new_name)
            return False
        
    def copy(self, target_app: App) -> str:
        """
        Copy the measure to another app

        Args: target_app (App): The target app, where the measure will be copied
        Returns: str: ID of the measure created if successful, None otherwise
        """

        if target_app.measures.count == 0: target_app.measures.load()
        return target_app.measures.add(source = self)
        
    def get_layout(self) -> dict:
        """
        Returns the layout of the measure
        """
        logger.debug('Measure.get_layout function started, %s', self.name)
        self.get_handle()
        return _get_layout(self.parent.ws, self.handle)
    
    def get_properties(self) -> dict:
        """
        Returns the properties of the measure
        """
        logger.debug('Measure.get_properties function started, %s', self.name)
        self.get_handle()
        return _get_properties(self.parent.ws, self.handle)


class Dimension:
    """
    The class, representing the master dimensions of the application
    Member of the App.dimensions collection
    """
    def __init__(self, parent, dimName):
        self.name = dimName

        self.parent = parent
        self.ws = parent.ws
        self.app_handle = parent.app_handle
        self.handle = 0
        
        self.id, self.definition, self.label, self.label_expression, self.description = '', '', '', '', ''
        self.created_date, self.modified_date = dt.datetime(year=1901, month=1, day=1), dt.datetime(year=1901, month=1, day=1)
        self.base_color = ''

    def __repr__(self):
        return f"Dimension(name={self.name!r}, id={self.id!r})"

    @staticmethod
    def _from_properties(parent, props: dict) -> 'Dimension':
        """Create a Dimension from a raw Engine API GetProperties response (qProp)."""
        title = props.get('qMetaDef', {}).get('title', '')
        dim = Dimension(parent, title)
        dim.app_handle = parent.app_handle
        dim.id = props.get('qInfo', {}).get('qId', '')
        qd = props.get('qDim', {})
        raw_defs = qd.get('qFieldDefs')
        dim.definition = raw_defs if isinstance(raw_defs, list) else []
        raw_labels = qd.get('qFieldLabels')
        dim.label = raw_labels if isinstance(raw_labels, list) else []
        coloring = qd.get('coloring', {})
        dim.base_color = coloring.get('baseColor', {}).get('color', '')
        dim.description = props.get('qMetaDef', {}).get('description', '')
        return dim

    def get_handle(self) -> int:
        """
        Get the handle of the dimension

        Returns:
            Handle of the dimension
        """
        logger.debug('Dimension.get_handle function started, name = %s', self.name)
        result = query(self.parent.ws, {
          "jsonrpc": "2.0",
          "id": _next_rpc_id(),
          "method": "GetDimension",
          "handle": self.app_handle,
          "params": [self.id]
        })
        if result is None or 'result' not in result:
            logger.error('Dimension.get_handle failed for %s', self.name)
            return None
        self.handle = result['result']['qReturn']['qHandle']
        logger.debug('Dimension.get_handle function completed, name = %s', self.name)
        return self.handle
    
    def update(self, definition: Union[str, List[str]] = None, label: Union[str, List[str]] = None, base_color: str = None) -> bool:
        """
        Update the dimension

        Args:
            definition (str): New definition of the dimension (string or list of strings)
            label (str): New label of the dimension (string or list of strings)

        Returns:
            True if the dimension was updated successfully, False otherwise
        """
        logger.debug('Dimension.update function started, name = %s', self.name)
        self.get_handle()

        def _normalize_dim_list(value):
            if value is None:
                return []
            if isinstance(value, list):
                return value
            if hasattr(value, 'tolist'):
                return value.tolist()
            if hasattr(value, '__iter__') and not isinstance(value, str):
                return list(value)
            try:
                if pd.isna(value):
                    return []
            except (ValueError, TypeError):
                pass
            return [value]

        definition = _normalize_dim_list(self.definition if definition is None else definition)
        label = _normalize_dim_list(self.label if label is None else label)
        if base_color is None:
            base_color = '' if pd.isna(self.base_color) else self.base_color

        t = {
          "jsonrpc": "2.0",
          "id": _next_rpc_id(),
          "method": "SetProperties",
          "handle": self.handle,
          "params": [
            {
              "qInfo": {
                "qId": self.id,
                "qType": "dimension"
              },
              "qDim": {
                  "qFieldLabels": label,
                  "qFieldDefs": definition,
                  "coloring": {'baseColor': {'color' : base_color}}
                },
                "qMetaDef": {'title': self.name}
            }
          ]
        }
        query_result = query(self.parent.ws, t)

        try:
            if 'change' in query_result and len(query_result['change']) > 0:
                self.definition = definition
                self.label = label
                self.base_color = base_color
                row_label = self.parent.df.index[self.parent.df['qInfo.qId'] == self.id].tolist()[0]
                self.parent.df.at[row_label, 'qDimFieldDefs'] = definition
                self.parent.df.at[row_label, 'qDimFieldLabels'] = label
                self.parent.df.at[row_label, 'qDimFieldBaseColor'] = base_color
                
                logger.info('Dimension updated: %s, new definition: %s, new label: %s', self.name, self.definition, self.label)
                return True
        except Exception as E:
            logger.exception('Failed to update dimension: %s, Error: %s', self.name, str(E))
            return False

        logger.error('Dimension.update completed without changes: %s', self.name)
        return False

    def delete(self) -> bool:
        """
        Delete the dimension

        Returns:
            True if the dimension was deleted successfully, False otherwise
        """

        logger.debug('Dimension.delete function started, name = %s', self.name)
        query_result = query(self.parent.ws, {
              "jsonrpc": "2.0",
              "id": _next_rpc_id(),
              "method": "DestroyDimension",
              "handle": self.app_handle,
              "params": [
                self.id
              ]
            })
        
        # delete value from dimensions collection
        if query_result is None or 'result' not in query_result or 'qSuccess' not in query_result['result']:
            logger.error('Failed to delete dimension, unexpected response: %s', query_result)
            return False

        if query_result['result']['qSuccess']:
            del self.parent[self.name]
            self.parent.df = self.parent.df[self.parent.df['qInfo.qId'] != self.id]
            logger.info ('Dimension deleted: %s', self.name)
            return True
        else:
            logger.error('Failed to delete dimension: %s', self.name)
            return False
        
    
    
    def rename(self, new_name: str) -> bool:
        """
        Rename the dimension

        Args:
            new_name (str): New name of the dimension

        Returns:
            True if the dimension was renamed successfully, False otherwise
        """

        logger.debug('Dimension.rename function started, old_name = %s, new_name = %s', \
                     self.name, new_name)
        self.get_handle()
        old_name = self.name

        t = {
          "jsonrpc": "2.0",
          "id": _next_rpc_id(),
          "method": "SetProperties",
          "handle": self.handle,
          "params": [
            {
              "qInfo": {
                "qId": self.id,
                "qType": "dimension"
              },
                "qMetaDef": {'title': new_name}
            }
          ]
        }
        query_result = query(self.parent.ws, t)
        
        if 'change' in query_result:
            self.name = new_name
            self.parent.df.loc[self.parent.df['qInfo.qId'] == self.id, 'qMeta.title'] = new_name
            self.parent[new_name] = self.parent[old_name]
            del self.parent[old_name]
            logger.info('Dimension renamed, old_name = %s, new_name = %s', old_name, new_name)
            return True
        else:
            logger.error('Failed to rename dimension, old_name = %s, new_name = %s', old_name, new_name)
            return False
        
    def copy(self, target_app: App) -> str:
        """
        Copy the dimension to another app

        Args: target_app (App): The target app, where the dimension will be copied
        Returns: str: ID of the dimension created if successful, null otherwise
        """

        if target_app.dimensions.count == 0: target_app.dimensions.load()
        return target_app.dimensions.add(source = self)
        
    def get_layout(self) -> dict:
        """
        Returns the layout of the dimension
        """
        logger.debug('Dimension.get_layout function started, %s', self.name)
        self.get_handle()
        return _get_layout(self.parent.ws, self.handle)
    
    def get_properties(self) -> dict:
        """
        Returns the properties of the dimension
        """
        logger.debug('Dimension.get_properties function started, %s', self.name)
        self.get_handle()
        return _get_properties(self.parent.ws, self.handle)


class Sheet:
    """
    The class, representing the sheets of the application
    Member of the App.sheets collection
    """

    def __init__(self, parent, sheetName):
        self.name = sheetName
        
        self.parent = parent
        self.ws = parent.ws
        self.app_handle = parent.app_handle
        self.handle = 0
        
        self.id = ''
        self.description = ''
        self.created_date = dt.datetime(year=1901, month=1, day=1)
        self.modified_date = dt.datetime(year=1901, month=1, day=1)
        self.published = ''
        self.approved = ''
        self.owner_id = ''
        self.owner_name = ''
        
        from qsea.sheet_objects import SheetChildren
        self.objects = SheetChildren(self)

    def __repr__(self):
        return f"Sheet(name={self.name!r}, id={self.id!r})"

    @staticmethod
    def _from_layout(parent, layout: dict) -> 'Sheet':
        """Create a Sheet from a raw Engine API GetLayout response."""
        title = layout.get('qMeta', {}).get('title', '')
        sh = Sheet(parent, title)
        sh.app_handle = parent.app_handle
        sh.id = layout.get('qInfo', {}).get('qId', '')
        sh.description = layout.get('qMeta', {}).get('description', '')
        sh.published = layout.get('qMeta', {}).get('published', '')
        sh.approved = layout.get('qMeta', {}).get('approved', '')
        owner = layout.get('qMeta', {}).get('owner', {})
        sh.owner_id = owner.get('id', '')
        sh.owner_name = owner.get('name', '')
        meta = layout.get('qMeta', {})
        try:
            sh.created_date = dt.datetime.strptime(meta['createdDate'], '%Y-%m-%dT%H:%M:%S.%fZ')
        except (KeyError, ValueError, TypeError):
            pass
        try:
            sh.modified_date = dt.datetime.strptime(meta['modifiedDate'], '%Y-%m-%dT%H:%M:%S.%fZ')
        except (KeyError, ValueError, TypeError):
            pass
        return sh

    def get_handle(self) -> int:
        logger.debug('Sheet.get_handle function started, name = %s', self.name)
        result = query(self.parent.ws, {
              "jsonrpc": "2.0",
              "id": _next_rpc_id(),
              "method": "GetObject",
              "handle": self.app_handle,
              "params": [
                self.id
              ]
            })
        if result is None or 'result' not in result:
            logger.error('Sheet.get_handle failed for %s', self.name)
            return None
        self.handle = result['result']['qReturn']['qHandle']
        logger.debug('Sheet.get_handle function finished, handle = %s', self.handle)
        return self.handle

    def load(self) -> bool:
        # load sheet objects, a shotcut for SheetChildren.load()
        logger.debug('Sheet.load function started, name = %s', self.name)
        if self.objects.load(): return True
        else: return False

    def clear(self) -> bool:
        # clear all sheet objects
        logger.debug('Sheet.clear function started, name = %s', self.name)
        self.get_handle()
        
        # destroying all children
        res = query(self.parent.ws, {
            "jsonrpc": "2.0",
            "id": _next_rpc_id(),
            "method": "DestroyAllChildren",
            "handle": self.handle,
            "params": []
            })
        
        if 'result' not in res:
            logger.error('Sheet.clear function, DestroyAllChildren method failed, name = %s', self.name)
            return False
        
        # clear all cells
        current_properties = self.get_properties()
        current_properties['result']['qProp']['cells'] = []
        res = _set_properties(self.parent.ws, \
                                    self.handle, current_properties['result']['qProp'])

        if 'result' not in res:
            logger.error('Sheet.clear function, clearing cells failed, name = %s', self.name)
            return False
        
        self.load()
        logger.debug('Sheet.clear function finished, name = %s', self.name)
        return True
        
    def delete(self) -> bool:
        """
        Delete the sheet

        Returns:
            True if the sheet was deleted successfully, False otherwise
        """

        logger.debug('Sheet.delete function started, name = %s', self.name)
        query_result = query(self.parent.ws, {
              "jsonrpc": "2.0",
              "id": _next_rpc_id(),
              "method": "DestroyObject",
              "handle": self.app_handle,
              "params": [
                self.id
              ]
            })
        
        # delete value from sheets collection
        if 'result' in query_result and 'qSuccess' in query_result['result'] and query_result['result']['qSuccess']:
            del self.parent[self.name]
            self.parent.df = self.parent.df[self.parent.df['qInfo.qId'] != self.id]
            logger.info ('Sheet deleted: %s', self.name)
            return True
        else:
            logger.error('Failed to delete the sheet: %s', self.name)
            return False
        
    
    def copy(self, target_app: App, master_match: str = 'name') -> str:
        """
        Creates a copy of the sheet in the target app
        Args: target_app: App object
        Returns: str, ID of the new sheet if succesful, None otherwise
        """
        from qsea.app import App  # noqa: F811

        logger.debug('Sheet.copy function started, name = %s, target_app = %s', self.name, target_app.name)
        
        # check existence of a target sheet with the same name
        if target_app.sheets.count == 0: target_app.sheets.load()
        if self.name in target_app.sheets.df['qMeta.title'].tolist():
            logger.error('Sheet.copy function, sheet with the same name already exists in the target app, name = %s, target_app = %s', self.name, target_app.name)
            return None
        
        # create a blank sheet in a target app
        source_sheet_properties = self.get_properties()
        t = {
                "jsonrpc": "2.0",
                "id": _next_rpc_id(),
                "method": "CreateObject",
                "handle": target_app.handle,
                "params": [
                    source_sheet_properties['result']['qProp']
                    ]
                }
        t['params'][0]['title'] = self.name
        t['params'][0]['description'] = self.description
        query_result = query(target_app.ws, t)
        
        # to revise: add query_result check 

        target_app.sheets.load()
        target_sheet = target_app.sheets[self.name]

        # copy all objects to the new sheet
        self.objects.load()
        for obj in self.objects:
            try: 
                obj.copy(target_app, target_sheet, master_match = master_match, add_cells = False)
            except Exception as E: logger.exception('Sheet.copy function, copying object failed, name = %s, target_app = %s, error_text: %s', obj.name, target_app.name, E)

        return target_sheet.id

    def get_layout(self) -> dict:
        """
        Returns the layout of the sheet
        """
        logger.debug('Sheet.get_layout function started, %s', self.name)
        self.get_handle()
        return _get_layout(self.parent.ws, self.handle)
    
    def get_properties(self) -> dict:
        """
        Returns the properties of the sheet
        """
        logger.debug('Sheet.get_properties function started, %s', self.name)
        self.get_handle()
        return _get_properties(self.parent.ws, self.handle)


class Bookmark:
    """
    The class, representing the bookmarks of the application
    Member of the App.bookmarks collection
    """

    def __init__(self, parent, bookmarkName):
        self.name = bookmarkName
        
        self.parent = parent
        self.ws = parent.ws
        self.app_handle = parent.app_handle
        self.handle = 0
        
        self.id, self.owner_id, self.owner_user_id, self.owner_name, self.state_data, self.description = '', '', '', '', '', ''
        self.published, self.approved = 0, 0
        self.created_date, self.modified_date, self.publish_time = dt.datetime(year=1901, month=1, day=1), dt.datetime(year=1901, month=1, day=1), dt.datetime(year=1901, month=1, day=1)

    def __repr__(self):
        return f"Bookmark(name={self.name!r}, id={self.id!r})"

    @staticmethod
    def _from_layout(parent, layout: dict) -> 'Bookmark':
        """Create a Bookmark from a raw Engine API GetLayout response."""
        title = layout.get('qMeta', {}).get('title', '')
        bm = Bookmark(parent, title)
        bm.app_handle = parent.app_handle
        bm.id = layout.get('qInfo', {}).get('qId', '')
        bm.description = layout.get('qMeta', {}).get('description', '')
        bm.published = layout.get('qMeta', {}).get('published', 0)
        bm.approved = layout.get('qMeta', {}).get('approved', 0)
        owner = layout.get('qMeta', {}).get('owner', {})
        bm.owner_id = owner.get('id', '')
        bm.owner_user_id = owner.get('userId', '')
        bm.owner_name = owner.get('name', '')
        bookmark_data = layout.get('qBookmark', {})
        bm.state_data = bookmark_data.get('qStateData', '')
        meta = layout.get('qMeta', {})
        try:
            bm.created_date = dt.datetime.strptime(meta['createdDate'], '%Y-%m-%dT%H:%M:%S.%fZ')
        except (KeyError, ValueError, TypeError):
            pass
        try:
            bm.modified_date = dt.datetime.strptime(meta['modifiedDate'], '%Y-%m-%dT%H:%M:%S.%fZ')
        except (KeyError, ValueError, TypeError):
            pass
        return bm

    def get_handle(self) -> int:
        """
        Gets the handle of the bookmark
        """
        logger.debug('Bookmark.get_handle function started, %s', self.name)
        result = query(self.parent.ws, {
          "jsonrpc": "2.0",
          "id": _next_rpc_id(),
          "method": "GetBookmark",
          "handle": self.app_handle,
          "params": [self.id]
        })
        if result is None or 'result' not in result:
            logger.error('Bookmark.get_handle failed for %s', self.name)
            return None
        self.handle = result['result']['qReturn']['qHandle']
        logger.debug('Bookmark.get_handle function completed, %s', self.handle)
        return self.handle
        
    def get_layout(self) -> dict:
        """
        Returns the layout of the bookmark
        """
        logger.debug('Bookmark.get_layout function started, %s', self.name)
        self.get_handle()
        return _get_layout(self.parent.ws, self.handle)
