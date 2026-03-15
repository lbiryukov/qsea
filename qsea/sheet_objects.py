from __future__ import annotations

import uuid
from typing import List, Union, Optional, TYPE_CHECKING

import pandas as pd

from qsea._config import logger
from qsea._engine import query, _get_properties, _set_properties, _get_layout, _next_rpc_id
from qsea._loaders import (
    _get_sheet_objects_pandas,
    _get_object_ms_pandas,
    _get_object_dim_pandas,
    _get_object_subitem_pandas,
    _get_hypercube_data,
)
from qsea._selections import _clear_all, _get_field_handle, _select_field_values

if TYPE_CHECKING:
    from qsea.app import App
    from qsea.objects import Sheet


class ChildrenIterator:
    def __init__(self, children):
        self.children = children.children
        self._keys = list(children.children.keys())
        self._index = 0
        self._class_size = len(children.children)

    def __next__(self):
        if self._index < self._class_size:
            result = self.children[self._keys[self._index]]
            self._index +=1
            return result
        raise StopIteration



class ObjectDimension():
    """
    The class, representing the dimensions, used in the object on the sheet
    Member of the ObjectChildren collection
    """

    def __init__(self, parent, dimName):
        self.name = dimName

        self.parent = parent
        self.ws = parent.ws
        self.app_handle = parent.app_handle
        self.handle = 0
        self.sheet = parent.sheet
        self.sheet_handle = parent.sheet_handle
        self.object = parent.parent

        self.index = -1
        logger.debug('ObjectDimension class. type: %s', type(self.parent))
        
        self.id, self.library_id, self.definition, self.label, self.calc_condition = '', '', '', '', ''
        
    def update(self, definition: Union[str, List[str]] = None, label: Union[str, List[str]] = None\
               , calc_condition: str = None) -> bool:
        """
        Updates object dimension properties

        Args:
            definition (str): new definition of the dimension (string or list of strings)
            label (str): new label of the dimension (string or list of strings)
            calc_condition (str): new calc_condition of the dimension

        Returns:
            bool: True if success, False if failed
        """

        logger.debug('ObjectDimension.update started, name = %s, definition = %s, label = %s'\
                     , self.name, definition, label)   
        self.object.get_handle()

        # if definition or labels are strings, convert them to lists
        if isinstance(definition, str): definition = [definition]
        if isinstance(label, str): label = [label]

        # check if new values exists; if not, leave old values without change
        def gn(x, y):
            if y is None: 
                if pd.isna(x): return ''
                else: return x
            else: return y
            
        definition, label, calc_condition = \
            gn(self.definition, definition),                \
            gn(self.label, label),                          \
            gn(self.calc_condition, calc_condition)

        # receiving properties of parent object
        props_result = query(self.ws, {
              "jsonrpc": "2.0",
              "id": _next_rpc_id(),
              "method": "GetProperties",
              "handle": self.object.handle,
              "params": []
            })
        if props_result is None or 'result' not in props_result or 'qProp' not in props_result.get('result', {}):
            logger.error('ObjectDimension.update: GetProperties failed, object=%s, response=%s', self.object.name, props_result)
            return False
        old_properties = props_result['result']['qProp']
               
        # changing properties json
        try:
            old_properties['qHyperCubeDef']['qDimensions'][self.index]['qDef']['qFieldDefs'] = definition
            old_properties['qHyperCubeDef']['qDimensions'][self.index]['qDef']['qFieldLabels'] = label
            old_properties['qHyperCubeDef']['qDimensions'][self.index]['qCalcCondition']['qCond']['qv'] = calc_condition
        except Exception as E:
            logger.exception('Unable to change old properties of the dimension, error: %s', E)
            return False

        # setting new properties
        query_result = query(self.ws, {
              "jsonrpc": "2.0",
              "id": _next_rpc_id(),
              "method": "SetProperties",
              "handle": self.object.handle,
              "params": [
                old_properties
                ]
            })
        
        try:
            # updating properties of the dimension in case of success
            if 'change' in query_result and len(query_result['change']) > 0:
                self.definition = definition
                self.label = label
                self.calc_condition = calc_condition
                row_label = self.parent.df.index[self.parent.df['qDef.cId'] == self.id].tolist()[0]
                self.parent.df.at[row_label, 'qDef.qFieldDefs'] = definition
                self.parent.df.at[row_label, 'qDef.qFieldLabels'] = label
                self.parent.df.at[row_label, 'qCalcCondition.qCond.qv'] = calc_condition

                logger.debug('ObjectDimension.update finished, sheet_name: %s, object_name: %s, dimension_id: %s', \
                             self.object.sheet.name, self.object.name, self.id)
                return True
            else:
                logger.error('Unable to update object dimension, sheet_name: %s, object_name: %s, dimension_id: %s', \
                                self.object.sheet.name, self.object.name, self.id)
                return False
        except Exception as E:
            logger.exception('Unable to update object dimension, sheet_name: %s, object_name: %s, dimension_id: %s, error: %s', \
                             self.object.sheet.name, self.object.name, self.id, E)
            return False
    
    def delete(self):
        """
        Unchecked function, use with caution
        """
        logger.debug('ObjectDimension.delete started, name = %s', self.name)
        self.object.get_handle()

        # receiving properties of parent object
        props_result = query(self.ws, {
              "jsonrpc": "2.0",
              "id": _next_rpc_id(),
              "method": "GetProperties",
              "handle": self.object.handle,
              "params": []
            })
        if props_result is None or 'result' not in props_result or 'qProp' not in props_result.get('result', {}):
            logger.error('ObjectDimension.delete: GetProperties failed, object=%s, response=%s', self.object.name, props_result)
            return None
        t = props_result['result']['qProp']
               
        # deleting item properties json
        t['qHyperCubeDef']['qDimensions'].pop(self.index)
        t['qHyperCubeDef']['qInterColumnSortOrder'].remove(max(t['qHyperCubeDef']['qInterColumnSortOrder']))
        t['qHyperCubeDef']['qColumnOrder'].remove(max(t['qHyperCubeDef']['qColumnOrder']))
        t['qHyperCubeDef']['columnOrder'].remove(max(t['qHyperCubeDef']['columnOrder']))
        t['qHyperCubeDef']['columnWidths'].pop(self.index)   # здесь  неправильно - не ясно какую колонку на самом деле мы удаляем
        
        set_result = query(self.ws, {
              "jsonrpc": "2.0",
              "id": _next_rpc_id(),
              "method": "SetProperties",
              "handle": self.object.handle,
              "params": [
                t
                ]
            })
        
        if 'change' in set_result:
            logger.info('ObjectDimension.delete, Dimension deleted: %s', self.name)
            del self.parent[self.name]
        else: logger.error('ObjectDimension.delete, Failed to delete dimension: %s', self.name)
        
        return set_result



class ObjectMeasure():
    """
    The class, representing the measures, used in the object on the sheet
    Member of the ObjectChildren collection
    """
    def __init__(self, parent, msName):
        self.name = msName
        
        self.parent = parent
        self.ws = parent.ws
        self.app_handle = parent.app_handle
        self.handle = 0
        self.sheet = parent.sheet
        self.sheet_handle = parent.sheet_handle
        self.object = parent.parent

        self.index = -1
        
        self.id, self.library_id, self.definition, self.label, self.label_expression, \
            self.calc_condition, self.library_id = '', '', '', '', '', '', ''
        self.format_type, self.format_ndec, self.format_use_thou, self.format_dec, self.format_thou = '', -1, -1, '', ''
        
    def update(self, definition: str = None, label: str = None, label_expression: str = None, \
               calc_condition: str = None, library_id: str = None, format_type: str = None, \
                format_use_thou: int = -1, format_dec: str = None, format_thou: str = None) -> bool:
        """
        Updates measure properties

        Args:
            definition (str, optional): New definition of the measure
            label (str, optional): New  label of the measure
            label_expression (str, optional): New label expression of the measure
            calc_condition (str, optional): New calculation condition of the measure
            library_id (str, optional): New library_id (library_id is a link to a master measure)
            format_type (str, optional): New format type of the measure
                'U' for auto
                'F' for number
                'M' for money
                'D' for date
                'IV' for duration
                'R' for other
            format_use_thou (int, optional): New use thousands flag of the measure
            format_dec (str, optional): New decimal separator of the measure
            format_thou (str, optional): New thousand separator of the measure

        Returns:
            bool: True if success, False if failed
        """

        self.object.get_handle()
        logger.debug('ObjectMeasure.update started, name = %s, definition = %s, label = %s', self.name, definition, label)
        # check if new values exists; if not, leave old values without change
        def gn(x, y):
            if y is None: 
                if pd.isna(x): return ''
                else: return str(x)
            else: return str(y)
            
        # check if new values exists; if not, leave old values without change
        def fn(x, y):
            if y == -1: 
                if pd.isna(x): return 0
                else: return x
            else: return y

        definition, label, label_expression, calc_condition, library_id, format_type, \
            format_use_thou, format_dec, format_thou = \
            gn(self.definition, definition), \
            gn(self.label, label),\
            gn(self.label_expression, label_expression),\
            gn(self.calc_condition, calc_condition),\
            gn(self.library_id, library_id),\
            gn(self.format_type, format_type),\
            fn(self.format_use_thou, format_use_thou),\
            gn(self.format_dec, format_dec),\
            gn(self.format_thou, format_thou)

        # receiving properties of parent object
        props_result = query(self.ws, {
              "jsonrpc": "2.0",
              "id": _next_rpc_id(),
              "method": "GetProperties",
              "handle": self.object.handle,
              "params": []
            })
        if props_result is None or 'result' not in props_result or 'qProp' not in props_result.get('result', {}):
            logger.error('ObjectMeasure.update: GetProperties failed, object=%s, response=%s', self.object.name, props_result)
            return False
        old_properties = props_result['result']['qProp']
               
        # changing properties json
        try:
            qdef = old_properties['qHyperCubeDef']['qMeasures'][self.index]['qDef']
            qdef['qDef'] = definition
            qdef['qLabel'] = label
            qdef['qLabelExpression'] = label_expression
            old_properties['qHyperCubeDef']['qMeasures'][self.index]['qCalcCondition']['qCond']['qv'] = calc_condition
            old_properties['qHyperCubeDef']['qMeasures'][self.index]['qLibraryId'] = library_id
            # qNumFormat may be missing when numFormatFromTemplate is True (library measure)
            qfmt = qdef.setdefault('qNumFormat', {})
            qfmt['qType'] = format_type
            # qnDec (number of decimals) is not implemented correctly by Qlik Sense - 09.07.2023
            qfmt['qUseThou'] = format_use_thou
            qfmt['qDec'] = format_dec
            qfmt['qThou'] = format_thou
        except Exception as E:
            logger.exception('Unable to change old properties of the measure, error: %s', E) 
            return False
        
        # setting new properties
        query_result = query(self.ws, {
              "jsonrpc": "2.0",
              "id": _next_rpc_id(),
              "method": "SetProperties",
              "handle": self.object.handle,
              "params": [
                old_properties
                ]
            })
        
        try:
            # updating properties of the measure in case of success
            if 'change' in query_result and len(query_result['change']) > 0:
                self.definition = definition
                self.label = label
                self.label_expression = label_expression
                self.calc_condition = calc_condition
                self.library_id = library_id
                self.format_type = format_type
                self.format_use_thou = format_use_thou
                self.format_dec = format_dec
                self.format_thou = format_thou

                row_label = self.parent.df.index[self.parent.df['qDef.cId'] == self.id].tolist()[0]
                self.parent.df.at[row_label, 'qDef.qDef'] = definition
                self.parent.df.at[row_label, 'qDef.qLabel'] = label
                self.parent.df.at[row_label, 'qDef.qLabelExpression'] = label_expression
                self.parent.df.at[row_label, 'qCalcCondition.qCond.qv'] = calc_condition
                self.parent.df.at[row_label, 'qLibraryId'] = library_id
                self.parent.df.at[row_label, 'qDef.qNumFormat.qType'] = format_type
                self.parent.df.at[row_label, 'qDef.qNumFormat.qUseThou'] = format_use_thou
                self.parent.df.at[row_label, 'qDef.qNumFormat.qDec'] = format_dec
                self.parent.df.at[row_label, 'qDef.qNumFormat.qThou'] = format_thou

                logger.debug('ObjectMeasure.update finished, sheet_name: %s, object_name: %s, measure_id: %s', \
                             self.object.sheet.name, self.object.name, self.id)
                return True
            else:
                logger.error('Unable to update object measure, sheet_name: %s, object_name: %s, measure_id: %s', \
                                self.object.sheet.name, self.object.name, self.id)
                return False
        except Exception as E:
            logger.exception('Unable to update object measure, sheet_name: %s, object_name: %s, measure_id: %s, error: %s', \
                             self.object.sheet.name, self.object.name, self.id, str(E))
            return False
        
    
    def delete(self):
        """
        Unchecked function, use with caution
        """
        logger.debug('ObjectMeasure.delete started, name = %s', self.name)
        self.object.get_handle()

        # receiving properties of parent object
        props_result = query(self.ws, {
              "jsonrpc": "2.0",
              "id": _next_rpc_id(),
              "method": "GetProperties",
              "handle": self.object.handle,
              "params": []
            })
        if props_result is None or 'result' not in props_result or 'qProp' not in props_result.get('result', {}):
            logger.error('ObjectMeasure.delete: GetProperties failed, object=%s, response=%s', self.object.name, props_result)
            return None
        t = props_result['result']['qProp']
               
        # deleting item properties json
        t['qHyperCubeDef']['qMeasures'].pop(self.index)
        t['qHyperCubeDef']['qInterColumnSortOrder'].remove(max(t['qHyperCubeDef']['qInterColumnSortOrder']))
        t['qHyperCubeDef']['qColumnOrder'].remove(max(t['qHyperCubeDef']['qColumnOrder']))
        t['qHyperCubeDef']['columnOrder'].remove(max(t['qHyperCubeDef']['columnOrder']))
        t['qHyperCubeDef']['columnWidths'].pop(self.index)   # здесь  неправильно - не ясно какую колонку на самом деле мы удаляем
        
        set_result = query(self.ws, {
              "jsonrpc": "2.0",
              "id": _next_rpc_id(),
              "method": "SetProperties",
              "handle": self.object.handle,
              "params": [
                t
                ]
            })
        
        if 'change' in set_result:
            logger.info('Measure deleted: %s', self.name)
            del self.parent[self.name]
        else: logger.error('Failed to delete measure: %s', self.name)
        
        return set_result



class ObjectChildren():
    """
    The class, representing different collections of sheet objects, like measures or dimensions
    """
    def __init__(self, parent, _type):
        self.parent = parent
        self.ws = parent.ws
        self.app_handle = parent.app_handle
        self.handle = 0
        self.sheet = parent.sheet
        self.sheet_handle = parent.sheet_handle
        self.object = parent.parent
        
        self.children = {}
        self.count = 0
        self._type = _type
    
    def __getitem__(self, childCaller):
        logger.debug('ObjectChildren.__getitem__ started, sheet = %s, childCaller = %s', self.sheet.name, childCaller)
        
                        
        if isinstance(childCaller, str):
            return self.children[childCaller]
        else:
            for ch in self.children.keys():
                logger.debug(self.children[ch].index)
                if self.children[ch].index == childCaller: return self.children[ch]
    
    def __setitem__(self, childCaller, var):
        logger.debug('ObjectChildren.__setitem__ started, childCaller = %s', childCaller)
        self.children[childCaller] = var
            
    def __delitem__(self, childCaller):
        logger.debug('ObjectChildren.__delitem__ started, childCaller = %s', childCaller)
        del self.children[childCaller]
        self.count -= 1
            
    def __iter__(self):
        logger.debug('ObjectChildren.__iter__ started, %s, %s', self.parent.name, self._type)
        if self.count == 0:
            try: zvb = self['']
            except KeyError: pass
        return ChildrenIterator(self)

    def __len__(self):
        return self.count

    def __contains__(self, key):
        return key in self.children

    def __repr__(self):
        return f"ObjectChildren(type={self._type!r}, count={self.count})"

    def load(self) -> bool:
        """
        Loads object dimensions or measures from Qlik Sense
        """
        logger.debug('ObjectChildren.load started, sheet = %s, object = %s, _type = %s', self.sheet.name, self.parent.name, self._type)

        def pick(row, colName, _type = str):
            if colName in row.index:
                if pd.isna(row[colName]): 
                    if _type == str: return ''
                    else: return 0
                else: return row[colName]
            else: 
                if _type == str: return ''
                else: return 0

        self.count = 0
        self.children = {}

        if self._type == 'objectDimensions':
            self.parentHandle = self.parent.get_handle()
            if self.parentHandle is None:   # upd 16.08.2024
                logger.warning('Unable to retrieve handle for the object %s', self.parent.name)
                return False
            try:
                self.df = _get_object_dim_pandas(self.ws, self.parentHandle)
                if len(self.df) == 0:
                    logger.debug('No dimensions found for the object %s', self.parent.name)
                    return True
                # since some cId can be empty, we need to fill them with some values; qsea_id column marks those values
                mask = self.df['qDef.cId'].isnull()
                self.df['qDef.cId'] = self.df['qDef.cId'].apply(lambda x: str(uuid.uuid4()) if pd.isnull(x) else x)
                self.df.loc[mask, 'qsea_id'] = 1
                self.df['qsea_id'] = self.df['qsea_id'].fillna(0)

                for dimId in self.df['qDef.cId']:
                    dim = ObjectDimension(self, dimId)
                    dim.app_handle = self.app_handle
                    dim.index = self.count
                    
                    row = self.df[self.df['qDef.cId'] == dimId].iloc[0]
                    dim.id = dimId
                    dim.qsea_id = pick(row, 'qsea_id')
                    dim.library_id = pick(row, 'qLibraryId')
                    dim.definition = pick(row, 'qDef.qFieldDefs')
                    dim.label = pick(row, 'qDef.qFieldLabels')
                    dim.label_expression = pick(row, 'qDef.qLabelExpression')
                    dim.calc_condition = pick(row, 'qCalcCondition.qCond.qv')

                    self[dimId] = dim
                    self.count += 1
            except Exception as e:
                logger.warning('Unable to retrieve dimensions for the object %s: %s', self.parent.name, e)
                return False

        if self._type == 'objectMeasures':
            self.parentHandle = self.parent.get_handle()
            if self.parentHandle is None:
                logger.warning('Unable to retrieve handle for the object %s', self.parent.name)
                return False
            logger.debug('parentHandle: %s', self.parentHandle)
            try: 
                self.df = _get_object_ms_pandas(self.ws, self.parentHandle)
                if len(self.df) == 0:
                    logger.debug('No measures found for the object %s', self.parent.name)
                    return True
                
                # since some cId can be empty, we need to fill them with some values; qsea_id column marks those values
                mask = self.df['qDef.cId'].isnull()
                self.df['qDef.cId'] = self.df['qDef.cId'].apply(lambda x: str(uuid.uuid4()) if pd.isnull(x) else x)
                self.df.loc[mask, 'qsea_id'] = 1
                self.df['qsea_id'] = self.df['qsea_id'].fillna(0)

                for msId in self.df['qDef.cId']:
                    ms = ObjectMeasure(self, msId)
                    ms.app_handle = self.app_handle
                    ms.index = self.count

                    row = self.df[self.df['qDef.cId'] == msId].iloc[0]
                    ms.id = msId
                    ms.library_id = pick(row, 'qLibraryId')
                    ms.definition = pick(row, 'qDef.qDef')
                    ms.label = pick(row, 'qDef.qLabel')
                    ms.label_expression = pick(row, 'qDef.qLabelExpression')
                    ms.calc_condition = pick(row, 'qCalcCondition.qCond.qv')
                    ms.format_type = pick(row, 'qDef.qNumFormat.qType')
                    ms.format_ndec = pick(row, 'qDef.qNumFormat.qnDec', int)
                    ms.format_use_thou = pick(row, 'qDef.qNumFormat.qUseThou', int)
                    ms.format_dec = pick(row, 'qDef.qNumFormat.qDec')
                    ms.format_thou = pick(row, 'qDef.qNumFormat.qThou')

                    self[msId] = ms
                    self.count += 1
            except Exception as e:
                logger.warning('Unable to retrieve measures for the object %s: %s', self.parent.name, e)
                return False

        if self._type == 'objectSubItems':
            self.parentHandle = self.parent.get_handle()
            if self.parentHandle is None:
                logger.warning('Unable to retrieve handle for the object %s', self.parent.name)
                return False
            logger.debug('parentHandle: %s', self.parentHandle)
            try: 
                self.df = _get_object_subitem_pandas(self.ws, self.parentHandle)
                if len(self.df) == 0:
                    logger.debug('No subitems found for the object %s', self.parent.name)
                    return True
                
                for objId in self.df['qId']:
                    obj = Object(self, objId)
                    obj.index = self.count

                    row = self.df[self.df['qId'] == objId].iloc[0]
                    obj.id = objId
                    obj.type = pick(row, 'qType')

                    self[objId] = obj
                    obj.load()
                    self.count += 1
            except Exception as e:
                logger.warning('Unable to retrieve subitems for the object %s: %s', self.parent.name, e)
                return False
        # else:
        #     logger.warning('ObjectChildren.load function, %s already loaded, recreate the App object to reload', self._type)
        #     return False
        logger.debug('ObjectChildren.load finished, sheet = %s, object = %s, _type = %s', self.sheet.name, self.parent.name, self._type)
        return True
            
    def add(self, definition = '', label = '', label_expression = '', library_id = '',\
            format_type = '', format_ndec = -1, format_use_thou = -1, format_dec = '',\
            format_thou = ''):
        # unchecked function, use with caution
        self.parent.get_handle()
        if self._type == 'objectDimensions':
            
            # warnings
            if label_expression != '': logger.warning("label_expression can't be used with dimensions, field will be ignored")
            if format_type != '': logger.warning("format_type can't be used with dimensions, field will be ignored")
            if format_ndec != -1: logger.warning("format_ndec can't be used with dimensions, field will be ignored")
            if format_use_thou != -1: logger.warning("format_use_thou can't be used with dimensions, field will be ignored")
            if format_dec != '': logger.warning("format_dec can't be used with dimensions, field will be ignored")
            if format_thou != '': logger.warning("format_thou can't be used with dimensions, field will be ignored")

            # receiving properties of parent object
            props_result = query(self.ws, {
                  "jsonrpc": "2.0",
                  "id": _next_rpc_id(),
                  "method": "GetProperties",
                  "handle": self.parent.handle,
                  "params": []
                })
            if props_result is None or 'result' not in props_result or 'qProp' not in props_result.get('result', {}):
                logger.error('ObjectChildren.add: GetProperties failed, object=%s, response=%s', self.parent.name, props_result)
                return None
            t = props_result['result']['qProp']
            
            # changing properties json
            # length of dimensions list
            
            if library_id == '':
                t['qHyperCubeDef']['qDimensions'].append({'qDef': 
                                                      {'qGrouping': 'N', 
                                                       'qFieldDefs': [definition], 
                                                       'qFieldLabels': [label], 
                                                       #'qLabelExpression': [label_expression],
                                                       'qSortCriterias': [{'qSortByNumeric': 1
                                                                           , 'qSortByAscii': 1
                                                                           , 'qSortByLoadOrder': 1
                                                                           , 'qExpression': {}}], 
                                                       'qNumberPresentations': [], 
                                                       'qActiveField': 0, 
                                                       'autoSort': True, 
                                                       #'cId': 'NbjUkqwer', 
                                                       'othersLabel': 'Другие', 
                                                       'textAlign': {'auto': True, 'align': 'left'}, 
                                                       'representation': {'type': 'text', 
                                                                          'urlPosition': 'dimension', 
                                                                          'urlLabel': '', 'linkUrl': ''}}, 
                                                      'qOtherTotalSpec': {'qOtherMode': 'OTHER_OFF', 
                                                                          'qOtherCounted': {'qv': '10'}, 
                                                                          'qOtherLimit': {'qv': '0'}, 
                                                                          'qOtherLimitMode': 'OTHER_GE_LIMIT', 
                                                                          'qForceBadValueKeeping': True, 
                                                                          'qApplyEvenWhenPossiblyWrongResult': True, 
                                                                          'qOtherSortMode': 'OTHER_SORT_DESCENDING', 
                                                                          'qTotalMode': 'TOTAL_OFF', 
                                                                          'qReferencedExpression': {}}, 
                                                      'qOtherLabel': {'qv': 'Другие'}, 
                                                      'qTotalLabel': {}, 
                                                      'qCalcCond': {}, 
                                                      'qAttributeExpressions': [], 
                                                      'qAttributeDimensions': [], 
                                                      'qCalcCondition': {'qCond': {}, 'qMsg': {}}})
                
            if library_id != '':
                t['qHyperCubeDef']['qDimensions'].append({'qLibraryId': library_id,
                                                     'qDef': {'qGrouping': 'N',
                                                      'qFieldDefs': [],
                                                      'qFieldLabels': [],
                                                      'qSortCriterias': [{'qSortByNumeric': 1,
                                                        'qSortByAscii': 1,
                                                        'qSortByLoadOrder': 1,
                                                        'qExpression': {}}],
                                                      'qNumberPresentations': [],
                                                      'qActiveField': 0,
                                                      'autoSort': True,
                                                      #'cId': 'VwGrKh',
                                                      'othersLabel': 'Другие',
                                                      'textAlign': {'auto': True, 'align': 'left'},
                                                      'representation': {'type': 'text',
                                                       'urlPosition': 'dimension',
                                                       'urlLabel': '',
                                                       'linkUrl': ''}},
                                                     'qOtherTotalSpec': {'qOtherMode': 'OTHER_OFF',
                                                      'qOtherCounted': {'qv': '10'},
                                                      'qOtherLimit': {'qv': '0'},
                                                      'qOtherLimitMode': 'OTHER_GE_LIMIT',
                                                      'qForceBadValueKeeping': True,
                                                      'qApplyEvenWhenPossiblyWrongResult': True,
                                                      'qOtherSortMode': 'OTHER_SORT_DESCENDING',
                                                      'qTotalMode': 'TOTAL_OFF',
                                                      'qReferencedExpression': {}},
                                                     'qOtherLabel': {'qv': 'Другие'},
                                                     'qTotalLabel': {},
                                                     'qCalcCond': {},
                                                     'qAttributeExpressions': [],
                                                     'qAttributeDimensions': [],
                                                     'qCalcCondition': {'qCond': {}, 'qMsg': {}}
                                                         })

            t['qHyperCubeDef']['qInterColumnSortOrder'].append(max(t['qHyperCubeDef']['qInterColumnSortOrder']) + 1)
            t['qHyperCubeDef']['qColumnOrder'].append(max(t['qHyperCubeDef']['qColumnOrder']) + 1)
            t['qHyperCubeDef']['columnOrder'].append(max(t['qHyperCubeDef']['columnOrder']) + 1)
            t['qHyperCubeDef']['columnWidths'].append(-1)   # здесь  неправильно - не ясно какую колонку на самом деле мы удаляем

            logger.debug(t)
            
            set_result = query(self.ws, {
                  "jsonrpc": "2.0",
                  "id": _next_rpc_id(),
                  "method": "SetProperties",
                  "handle": self.parent.handle,
                  "params": [
                    t
                    ]
                })

            self.definition = definition
            self.label = label
            self.label_expression = label_expression

            return [t, set_result]


class Object:
    """
    The class, representing the objects on the sheet, such as charts and tables.
    Member of the SheetChildren collection
    """
    def __init__(self, parent, objName):
        self.name = objName

        self.parent = parent
        self.ws = parent.ws
        self.app_handle = parent.app_handle
        self.handle = 0
        self.sheet = parent.sheet
        self.sheet_handle = parent.sheet_handle
        
        self.type = ''
        self.col, self.row, self.colspan, self.rowspan, self.bounds_y, self.bounds_x, self.bounds_width, self.bounds_height = 0, 0, 0, 0, 0, 0, 0, 0
        
        self.dimensions = ObjectChildren(self, 'objectDimensions')
        self.measures = ObjectChildren(self, 'objectMeasures')
        self.subitems = ObjectChildren(self, 'objectSubItems')

    def __repr__(self):
        return f"Object(name={self.name!r}, type={self.type!r})"

    def get_handle(self) -> int:
        """
        Returns the handle of the object
        """

        logger.debug('Object.get_handle started, sheet = %s, name = %s, id = %s, app_handle = %s'\
                     , self.sheet.name, self.name, self.id, self.app_handle)
        result = query(self.ws, {
          "jsonrpc": "2.0",
          "id": _next_rpc_id(),
          "method": "GetObject",
          "handle": self.app_handle,
          "params": [self.id]
        })
        if result is None or 'result' not in result:
            logger.error('Object.get_handle failed for %s', self.name)
            return None
        self.handle = result['result']['qReturn']['qHandle']
        logger.debug('Object.get_handle finished, handle = %s', self.handle)
        return self.handle

    def load(self) -> bool:
        """
        Loads object dimensions and measures from Qlik Sense
        """
        logger.debug('Object.load started, sheet = %s, name = %s', self.sheet.name, self.name)
        self.get_handle()
        try:
            if self.type not in ('filterpane', 'container'): self.dimensions.load()
            if self.type not in ('filterpane', 'container', 'listbox'): self.measures.load()
            if self.type in ('filterpane', 'container'): self.subitems.load()
            logger.debug('Object.load finished, dimensions = %s, measures = %s, subitems = %s', \
                        self.dimensions.count, self.measures.count, self.subitems.count)
            return True
        except Exception as e:
            logger.warning('Object.load failed, sheet = %s, name = %s, error: %s', self.sheet.name, self.name, e)
            return False
        
    def export_data(self, file_type: str = 'xlsx') -> None:
        """
        Exports data from the object to xlsx or csv file
        Args: file_type, 'xlsx' or 'csv', 'xlsx' by default
        Returns the path to the downloaded file in case of success, None if failed
        """

        logger.debug('Object.export_data started, sheet = %s, name = %s, id = %s, file_type = %s', \
                     self.sheet.name, self.name, self.id, file_type)
        if file_type not in ['xlsx', 'csv']:
            logger.error('Object.export_data failed, sheet = %s, name = %s, id = %s, file_type = %s, error: incorrect file type', \
                         self.sheet.name, self.name, self.id, file_type)
            return None
        
        self.get_handle()
        if file_type == 'xlsx':
            t = {
                "jsonrpc": "2.0",
                "id": _next_rpc_id(),
                "method": "ExportData",
                "handle": self.handle,
                "params": [
                    "OOXML",
                    "/qHyperCubeDef"
                ]
                }
        if file_type == 'csv':
            t = {
                "jsonrpc": "2.0",
                "id": _next_rpc_id(),
                "method": "ExportData",
                "handle": self.handle,
                "params": [
                    "CSV_C",
                    "/qHyperCubeDef",
                    "CsvUTF8.csv"
                ]
                }
        query_result = query(self.ws, t)
        if 'result' in query_result and 'qUrl' in query_result['result']:
            logger.info('Object.export_data finished, sheet = %s, name = %s, id = %s, file_type = %s', \
                         self.sheet.name, self.name, self.id, file_type)
            return query_result['result']['qUrl']   
        
        logger.error('Object.export_data failed, sheet = %s, name = %s, id = %s, file_type = %s, error: %s', \
                     self.sheet.name, self.name, self.id, file_type, query_result)

    def get_data(self, filters: dict = None,
                 validate_filters: bool = True) -> Optional[pd.DataFrame]:
        """
        Fetches the object's hypercube data and returns it as a pandas DataFrame.

        Dimensions are returned as text columns, measures as numeric (with text
        fallback for non-numeric cells).  Pagination is handled automatically
        for datasets exceeding the Engine API limit of 10 000 cells per request.

        Args:
            filters (dict, optional): field -> value(s) filter. Values can be
                int, float, str, or list of these types.
                Example: {"Year": 2025, "Month": [1, 2]}
                When provided, applies temporary field selections before fetching
                data and clears them afterwards.
            validate_filters (bool): if True (default), validates that filter
                field names exist in the data model and that filter values exist
                in their fields. Set to False to skip validation for better
                performance.

        Returns:
            pd.DataFrame on success, None if the object type has no hypercube
            (e.g. filterpane, listbox).

        Raises:
            ValueError: if filter field names or values are invalid
                (when validate_filters=True)
        """
        logger.debug('Object.get_data started, sheet = %s, name = %s, id = %s, filters = %s',
                      self.sheet.name, self.name, self.id, filters)

        if self.type in ('filterpane', 'listbox'):
            logger.warning('Object.get_data: object type "%s" has no standard hypercube, '
                           'sheet = %s, name = %s', self.type, self.sheet.name, self.name)
            return None

        if validate_filters and filters:
            app = self.sheet.parent.parent
            app._validate_filters(filters)

        try:
            handle = self.get_handle()
            if handle is None:
                logger.warning('Object.get_data: could not get handle for %s', self.name)
                return None

            if filters:
                _clear_all(self.ws, self.app_handle)
                for field_name, values in filters.items():
                    if not isinstance(values, list):
                        values = [values]
                    fh = _get_field_handle(self.ws, self.app_handle, field_name)
                    _select_field_values(self.ws, fh, values)

            try:
                df = _get_hypercube_data(self.ws, self.handle)
            finally:
                if filters:
                    _clear_all(self.ws, self.app_handle)

            logger.info('Object.get_data finished, sheet = %s, name = %s, shape = %s',
                        self.sheet.name, self.name, df.shape)
            return df
        except Exception as e:
            logger.error('Object.get_data failed, sheet = %s, name = %s, id = %s, error: %s',
                         self.sheet.name, self.name, self.id, e)
            return None

    def get_layout(self) -> dict:
        """
        Returns the layout of the object
        """
        logger.debug('Object.get_layout function started, %s', self.name)
        self.get_handle()
        return _get_layout(self.ws, self.handle)
    
    def get_properties(self) -> dict:
        """
        Returns the properties of the object
        """
        logger.debug('Object.get_properties function started, %s', self.name)
        self.get_handle()
        return _get_properties(self.ws, self.handle)
    
        
    def copy(self, target_app, target_sheet, col: int = None, row: int = None, colspan: int = None \
             , rowspan: int = None, master_match: str = 'name', add_cells: bool = True) -> str:
        """
        Copies the object to the target sheet

        Args:
            target_app (App): The target app, where the object will be copied
            target_sheet (Sheet): The target sheet, where the object will be copied
            col (int, optional): The column, where the object will be copied. Defaults to None. If None, the column of the source is used
            row (int, optional): The row, where the object will be copied. Defaults to None. If None, the row of the source is used
            colspan (int, optional): The column span of the object. Defaults to None. If None, the column span of the source is used
            rowspan (int, optional): The row span of the object. Defaults to None. If None, the row span of the source is used
            master_match (str, optional): Defines how to match master measures and dimensions in the object. Defaults to 'name'.
                Possible values:
                    - 'name': Match by name; the target object will be created with master measures with same names
                    - 'id': Match by id; the target object will be created with master measures with same ids
            add_cells (bool, optional): Defines if the cells of the object should be added to the target sheet. Defaults to True.
                Should be always true except 1:1 copy of the whole sheet.

        Returns:
            str: ID of the object created if successful, null otherwise
        """
        from qsea.app import App
        from qsea.objects import Sheet

        logger.debug('Object.copy started, sheet = %s, object_id = %s', self.sheet.name, self.name)

        # check necessary parametres
        if type(target_app) != App:
            logger.error('Object.copy function failed, type of target_app should be App')
            return False
        if type(target_sheet) != Sheet:
            logger.error('Object.copy function failed, type of target_sheet should be Sheet')
            return False
        
        if master_match not in ['name', 'id']:
            logger.error('Object.copy function failed, invalid value for master_match parameter, should be "name" or "id"')
            return False

        self.get_handle()

        # obtain the properties of the source object
        source_properties = _get_properties(self.ws, self.handle)

        # set master measure and master dimension relations
        source_app = self.sheet.parent.parent
        if source_app.measures.count == 0: source_app.measures.load()
        if source_app.dimensions.count == 0: source_app.dimensions.load()
        if target_app.measures.count == 0: target_app.measures.load()
        if target_app.dimensions.count == 0: target_app.dimensions.load()

        logger.debug('Object.copy, source_app.measures.count = %s, target_app.measures.count = %s', source_app.measures.count, target_app.measures.count)

        if master_match == 'name':
            measures_match = source_app.measures.df.merge(target_app.measures.df, \
                        how='left', left_on='qMeta.title', right_on='qMeta.title', \
                        suffixes=('_source', '_target'))[['qInfo.qId_source', 'qMeta.title', 'qInfo.qId_target']]
            
            dimensions_match = source_app.dimensions.df.merge(target_app.dimensions.df, \
                        how='left', left_on='qMeta.title', right_on='qMeta.title', \
                        suffixes=('_source', '_target'))[['qInfo.qId_source', 'qMeta.title', 'qInfo.qId_target']]

            if 'qHyperCubeDef' in source_properties['result']['qProp']:
                for ms in source_properties['result']['qProp']['qHyperCubeDef']['qMeasures']:
                    if 'qLibraryId' in ms:
                        ms_name = source_app.measures.df.loc[source_app.measures.df['qInfo.qId'] == ms['qLibraryId'], 'qMeta.title'].values[0]
                        if ms_name not in target_app.measures.df['qMeta.title'].values:
                            logger.warning('Object copy function warning: Master measure %s not found in target app', ms_name)
                        else:
                            ms['qLibraryId'] = measures_match.loc[measures_match['qMeta.title'] == ms_name, 'qInfo.qId_target'].values[0]

                for dim in source_properties['result']['qProp']['qHyperCubeDef']['qDimensions']:
                    if 'qLibraryId' in dim:
                        dim_name = source_app.dimensions.df.loc[source_app.dimensions.df['qInfo.qId'] == dim['qLibraryId'], 'qMeta.title'].values[0]
                        if dim_name not in target_app.dimensions.df['qMeta.title'].values:
                            logger.warning('Object copy function warning: Master dimension %s not found in target app', dim_name)
                        else:
                            dim['qLibraryId'] = dimensions_match.loc[dimensions_match['qMeta.title'] == dim_name, 'qInfo.qId_target'].values[0]

        
        def _isnullbounds(json, value):
            if value in json:
                if json[value] is None: return 0
                else: return json[value]
            else: return 0

        
        # get the source object coords
        source_sheet_properties = _get_properties(self.ws, self.sheet.handle)
        for cl in source_sheet_properties['result']['qProp']['cells']:
            if cl['name'] == self.name:
                if col is None: col = cl['col']
                if row is None: row = cl['row']
                if colspan is None: colspan = cl['colspan']
                if rowspan is None: rowspan = cl['rowspan']
                bounds_y = _isnullbounds(cl['bounds'], 'y')
                bounds_x = _isnullbounds(cl['bounds'], 'x')
                bounds_width = _isnullbounds(cl['bounds'], 'width')
                bounds_height = _isnullbounds(cl['bounds'], 'height')
                break

        logger.debug('bounds_y: %s, bounds_x: %s, bounds_width: %s, bounds_height: %s', bounds_y, bounds_x, bounds_width, bounds_height)
        
        # get handle of the target sheet
        target_sheet.get_handle()

        # create a child object on the target sheet
        create_child_answer = query(target_sheet.parent.ws, {
            "jsonrpc": "2.0",
            "id": _next_rpc_id(),
            "method": "CreateChild",
            "handle": target_sheet.handle,
            "params": [
                    source_properties['result']['qProp']
            ]
            })
        
        # get id of the created object
        if 'result' not in create_child_answer or \
                'qReturn' not in create_child_answer['result'] or \
                'qGenericId' not in create_child_answer['result']['qReturn']:
            logger.error('Could not create child object, answer: %s', create_child_answer)
            return False
        
        new_object_id = create_child_answer['result']['qReturn']['qGenericId']
        
        # maintaining complex objects such as filterpanes and containers
        self.subitems.load()
        if self.subitems.count > 0:
            target_sheet.load()
            target_handle = target_sheet.objects[new_object_id].get_handle()
            for sub in self.subitems:
                sub.get_handle()
                sub_source_properties = _get_properties(self.ws, sub.handle)
            
                create_child_answer = query(target_sheet.parent.ws, {
                    "jsonrpc": "2.0",
                    "id": _next_rpc_id(),
                    "method": "CreateChild",
                    "handle": target_handle,
                    "params": [
                            sub_source_properties['result']['qProp']
                    ]
                    })

        if add_cells:
            target_sheet_properties = _get_properties(target_sheet.parent.ws, target_sheet.handle)
            target_sheet_properties['result']['qProp']['cells'].append({'name': new_object_id,
                'type': self.type,
                'col': col,
                'row': row,
                'colspan': colspan,
                'rowspan': rowspan,
                'bounds': {'y': bounds_y,
                'x': bounds_x,
                'width': bounds_width,
                'height': bounds_height}})
            
            # apply the target sheet properties
            set_sheet_prop = _set_properties(target_sheet.parent.ws, \
                                            target_sheet.handle, target_sheet_properties['result']['qProp'])
            
            if 'result' in set_sheet_prop:
                return new_object_id
            else:
                return None
        
        return new_object_id



class SheetChildren():
    """
    The class, representing the collection of the objects on the sheet
    """
    def __init__(self, parent):
        self.parent = parent
        self.ws = parent.ws
        self.app_handle = parent.app_handle
        self.sheet = parent
        self.sheet_handle = parent.handle

        self.children = {}
        self.count = 0
        
    def __getitem__(self, childName):
        logger.debug('SheetChildren.__getitem__ started, name = %s', childName)
        
        
        return self.children[childName]
    
    def __setitem__(self, childName, var):
        logger.debug('SheetChildren.__setitem__ started, name = %s', childName)
        self.children[childName] = var
            
    def __delitem__(self, childName):
        logger.debug('SheetChildren.__delitem__ started, name = %s', childName)
        del self.children[childName]
        self.count -= 1
            
    def __iter__(self):
        # initializing collection if empty
        logger.debug('SheetChildren.__iter__ started')
        if self.count == 0:
            self.load()
        return ChildrenIterator(self)

    def __len__(self):
        return self.count

    def __contains__(self, key):
        return key in self.children

    def __repr__(self):
        return f"SheetChildren(count={self.count})"

    def load(self) -> bool:
        """
        Loads all sheer objects from Qlik Sense into the collection
        """
        logger.debug('SheetChildren.load started, %s', self.parent.name)
        self.count = 0
        self.children = {}

        self.sheet_handle = self.parent.get_handle()
        self.df = _get_sheet_objects_pandas(self.ws, self.sheet_handle)
        if len(self.df) == 0:
            logger.warning('SheetChildren.load function, no objects on the sheet %s', self.parent.name)
            return False
        else:
            for objName in self.df['name']:
                obj = Object(self, objName)
                obj.sheet_handle = self.sheet_handle

                row = self.df[self.df['name'] == objName].iloc[0]
                obj.id = objName
                obj.type = row['type']
                obj.col = row['col']
                obj.row = row['row']
                obj.colspan = row['colspan']
                obj.rowspan = row['rowspan']
                obj.bounds_y = row['bounds.y']
                obj.bounds_x = row['bounds.x']
                obj.bounds_width = row['bounds.width']
                obj.bounds_height = row['bounds.height']

                self[objName] = obj
                self.count += 1
        # else:
        #     logger.warning('SheetChildren.load function, objects already loaded, recreate the App object to reload')

        logger.debug('SheetChildren.load finished, %s objects loaded', self.count)
        return True
