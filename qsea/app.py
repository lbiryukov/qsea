from __future__ import annotations

import datetime as dt
import pandas as pd
from typing import TYPE_CHECKING

from qsea._config import logger
from qsea._engine import query, _open_connection, _open_doc, _get_layout, _next_rpc_id
from qsea._helpers import _build_set_modifier, _find_key
from qsea._selections import (_evaluate_expression, _clear_all,
                               _get_field_handle, _select_field_values,
                               _create_session_hypercube, _destroy_session_object)
from qsea._loaders import (_get_var_pandas, _get_ms_pandas,
                            _get_sheet_pandas, _get_field_pandas, _get_dim_pandas,
                            _get_bookmark_pandas, _get_name_id_index,
                            _get_single_variable as _get_single_variable_func,
                            _get_single_variable_by_id as _get_single_variable_by_id_func,
                            _get_single_measure as _get_single_measure_func,
                            _get_single_dimension as _get_single_dimension_func,
                            _get_single_sheet as _get_single_sheet_func,
                            _get_single_bookmark as _get_single_bookmark_func)
from qsea.sheet_objects import ChildrenIterator


class App:
    """
    The class, representing the Qlik Sense application
    """

    def __init__(self, conn, app_name):

        self.name = app_name
        
        # in case if app is created after the connection is established, reload app list
        if self.name not in conn.df['qDocName'].values:
            conn.reload_app_list()
            logger.debug('App list reloaded')

        if self.name not in conn.df['qDocName'].values:
            logger.error('App %s is not found', self.name)
            raise ValueError('App ' + self.name + ' is not found.')
        
        self.id = conn.df[conn.df['qDocName'] == self.name]['qDocId'].values[0]

        if conn.main_app_id is None:
            conn.main_app_id = self.id

        if self.id in conn.wss:
            self.ws = conn.wss[self.id]
            logger.debug('App %s reusing existing connection', self.name)
        else:
            conn.wss[self.id] = _open_connection(
                conn.qlik_url + self.id, conn.header_user, conn.timeout,
                verify_ssl=conn.verify_ssl)
            self.ws = conn.wss[self.id]
            logger.debug('App %s opened new connection', self.name)

        self.handle = _open_doc(self.ws, app_id=self.id)
        if self.handle == 0:
            logger.error('App %s could not be opened', self.name)
            try:
                conn.wss.pop(self.id, None)
                self.ws.close()
            except Exception:
                pass
            raise ValueError('App ' + self.name + ' could not be opened.')
            
        self.variables = AppChildren(self, 'variables')
        self.measures = AppChildren(self, 'measures')
        self.sheets = AppChildren(self, 'sheets')
        self.fields = AppChildren(self, 'fields')
        self.dimensions = AppChildren(self, 'dimensions')
        self.bookmarks = AppChildren(self, 'bookmarks')

    def __repr__(self):
        return f"App(name={self.name!r}, id={self.id!r})"

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        try:
            self.clear_selections()
        except Exception:
            pass
        return False

    def save(self):
        """
        Saves the application on the Qlik Sense Server
        """
        logger.debug('App.save function started, %s', self.name)
        query_result = query(self.ws, {
            "jsonrpc": "2.0",
            "id": _next_rpc_id(),
            "method": "DoSave",
            "handle": self.handle,
            "params": []
        })

        if 'change' in query_result and query_result['change'][0] == 1:
            logger.info('App.save function completed, %s', self.name)
            return True
        
        logger.error('App.save function completed, DoSave method returned incorrect response, %s', self.name)
        return False

    def reload_data(self) -> bool:
        """
        Reloads the data in the application on the Qlik Sense Server.

        Returns:
            True if the reload completed successfully, False otherwise.
        """
        logger.debug('App.reload_data function started, %s', self.name)
        
        query_result = query(self.ws, {
                "jsonrpc": "2.0",
                "id": _next_rpc_id(),
                "method": "DoReloadEx",
                "handle": self.handle,
                "params": []
            })

        if query_result is None or 'result' not in query_result:
            logger.error('App.reload_data failed, no valid response for %s', self.name)
            return False

        success = query_result['result'].get('qReturn', {}).get('qSuccess', False)
        if success:
            logger.info('App.reload_data completed successfully, %s', self.name)
        else:
            logger.warning('App.reload_data completed, but qSuccess is False for %s', self.name)
        return success
            

    def load(self, depth: int=1) -> bool:
        """
        Loads data from the application on the Qlik Sense Server into an App object

        Args:
            depth (int): depth of loading
                1 - app + variables, measures, sheets, fields, dimensions
                2 - everything from 1 + sheet objects
                3 - everything from 2 + object dimensions and measures
        """
        logger.debug('App.load function started, name = %s, depth = %s', self.name, depth)
        if depth >= 1:
            self.variables.load()
            self.measures.load()
            self.sheets.load()
            self.fields.load()
            self.dimensions.load()
            self.bookmarks.load()

        if depth >= 2:
            for sh in self.sheets:
                try:
                    sh.load()
                    if depth >= 3:
                        for obj in sh.objects:
                            if obj.type not in ('filterpane', 'container'):
                                try:
                                    obj.load()
                                except Exception as E:
                                    logger.warning('App.load function, error loading object. Object will be ignored. %s, %s', obj.name, str(E))
                except Exception as E: logger.warning('App.load function, error loading sheet. Sheet will be ignored. %s, %s', sh.name, str(E))
        logger.debug('App.load function completed, %s', self.name)
        return True


    def _clearGarbage(self):
        """
        Clears garbage; only for debug purposes
        """
        logger.debug('App._clearGarbage function started, %s', self.name)
        
        for var in self.variables:
            if '_pre_' in var.name:
                logger.info('Deleting variable %s, %s', var.name, var.definition)
                var.delete()

        for ms in self.measures:
            if '_pre_' in ms.name:
                logger.info('Deleting measure %s, %s', ms.name, ms.definition)
                ms.delete()

        for dim in self.dimensions:
            if '_pre_' in dim.name:
                logger.info('Deleting dimension %s, %s', dim.name, dim.definition)
                dim.delete()

        logger.debug('App._clearGarbage function completed, %s', self.name)


    def evaluate(self, expression: str, filters: dict = None, method: str = 'evaluate') -> dict:
        """
        Evaluates a Qlik expression and returns the result.

        Supports two modes:
        - method='evaluate' (default): uses EvaluateEx (no filters) or a session hypercube
          with qContextSetExpression (with filters). Does not modify selections.
        - method='selections': applies filters via field selections, evaluates via
          session hypercube, then clears selections. Modifies session state temporarily.

        Args:
            expression (str): Qlik expression or master measure name.
                If the name matches a loaded master measure, its definition/library ID is used.
            filters (dict, optional): field -> value(s) filter. Values can be int, float, str,
                or list of these types. Example: {"Year": 2025, "Month": [1, 2]}
            method (str): 'evaluate' (default) or 'selections'

        Returns:
            dict: {"value": float or None, "text": str, "is_numeric": bool}
        """
        logger.debug('App.evaluate started, expression=%s, filters=%s, method=%s',
                     expression, filters, method)

        if method not in ('evaluate', 'selections'):
            raise ValueError(f"Unknown method '{method}'. Use 'evaluate' or 'selections'.")

        is_master = False
        library_id = None
        definition = expression

        if expression in self.measures.children:
            is_master = True
            library_id = self.measures[expression].id
            definition = self.measures[expression].definition
            logger.debug('App.evaluate: resolved master measure "%s", id=%s', expression, library_id)

        if filters is None:
            result = _evaluate_expression(self.ws, self.handle, definition)
            logger.debug('App.evaluate completed (EvaluateEx, no filters), result=%s', result)
            return result

        if method == 'evaluate':
            set_modifier = _build_set_modifier(filters)
            hc_result = _create_session_hypercube(
                self.ws, self.handle,
                expression=None if is_master else definition,
                library_id=library_id if is_master else None,
                context_set_expression=set_modifier
            )
            _destroy_session_object(self.ws, self.handle, hc_result['id'])
            result = {"value": hc_result['value'], "text": hc_result['text'], "is_numeric": hc_result['is_numeric']}
            logger.debug('App.evaluate completed (hypercube + qContextSetExpression), result=%s', result)
            return result

        if method == 'selections':
            hc_result = None
            try:
                _clear_all(self.ws, self.handle)
                for field_name, values in filters.items():
                    if not isinstance(values, list):
                        values = [values]
                    fh = _get_field_handle(self.ws, self.handle, field_name)
                    _select_field_values(self.ws, fh, values)

                hc_result = _create_session_hypercube(
                    self.ws, self.handle,
                    expression=None if is_master else definition,
                    library_id=library_id if is_master else None
                )
                result = {"value": hc_result['value'], "text": hc_result['text'], "is_numeric": hc_result['is_numeric']}
                logger.debug('App.evaluate completed (selections + hypercube), result=%s', result)
                return result
            finally:
                if hc_result:
                    _destroy_session_object(self.ws, self.handle, hc_result['id'])
                _clear_all(self.ws, self.handle)


    def clear_selections(self) -> bool:
        """
        Clears all current selections in the app.

        Returns:
            bool: True if successful
        """
        return _clear_all(self.ws, self.handle)


    def select_values(self, field_name: str, values: list, toggle: bool = False) -> bool:
        """
        Selects values in a field.

        Args:
            field_name (str): name of the field to select in
            values (list): values to select (int, float, or str)
            toggle (bool): if True, uses toggle selection mode

        Returns:
            bool: True if successful
        """
        handle = _get_field_handle(self.ws, self.handle, field_name)
        return _select_field_values(self.ws, handle, values, toggle)



class AppChildren():
    """
    The class, representing different collections of app objects, like master measures or dimensions
    A child of App class

    Supports lazy-loading: collections are loaded from Engine API on first
    access (iteration, indexing, len, ``in``, ``.df``).  Call ``load()``
    explicitly to force a reload.
    """
    def __init__(self, parent, _type):
        self.parent = parent
        self.ws = parent.ws
        self.app_handle = parent.handle
        self._type = _type
        
        self.children = {}
        self.count = 0
        self._loaded = False
        self._df = None
        self._index = None

    @property
    def df(self):
        self._ensure_loaded()
        return self._df

    @df.setter
    def df(self, value):
        self._df = value

    def _ensure_loaded(self):
        if not self._loaded:
            self.load()

    def __getitem__(self, childName):
        logger.debug('AppChildren.__getitem__ function started, _type = %s, childName = %s', self._type, childName)
        self._ensure_loaded()
        return self.children[childName]
    
    def __setitem__(self, childName, var):
        logger.debug('AppChildren.__setitem__ function started, _type = %s, childName = %s', self._type, childName)
        self.children[childName] = var
            
    def __delitem__(self, childName):
        logger.debug('AppChildren.__delitem__ function started, _type = %s, childName = %s', self._type, childName)
        del self.children[childName]
        self.count -= 1
            
    def __iter__(self):
        logger.debug('AppChildren.__iter__ function started')
        self._ensure_loaded()
        return ChildrenIterator(self)

    def __len__(self):
        self._ensure_loaded()
        return self.count

    def __contains__(self, key):
        self._ensure_loaded()
        return key in self.children

    def __repr__(self):
        return f"AppChildren(type={self._type!r}, count={self.count}, loaded={self._loaded})"

    def load(self) -> bool:
        """
        Load the collection of objects from Qlik Sense app into the class instance
        """
        from qsea.objects import Variable, Field, Measure, Dimension, Sheet, Bookmark
        from qsea.sheet_objects import SheetChildren

        logger.debug('AppChildren.load function started, _type = %s', self._type)

        self._loaded = False
        self.count = 0
        self.children = {}

        if self._type == 'variables':
            self._df = _get_var_pandas(self.parent.ws, self.app_handle)
            if len(self._df) == 0:
                logger.debug('AppChildren.load function, no variables found')
                self._loaded = True
                return True
            for varName in self._df['qName']:
                if pd.notna(varName):
                    var = Variable(self, varName)
                    var.app_handle = self.app_handle
                    
                    row = self._df[self._df['qName'] == varName].iloc[0]
                    var.id = row['qInfo.qId']
                    if 'qDefinition' in self._df.columns: var.definition = row['qDefinition']
                    if 'qDescription' in self._df.columns: var.description = row['qDescription']
                    if 'qIsScriptCreated' in self._df.columns: var.script_created = row['qIsScriptCreated']
                    if pd.isna(var.script_created): var.script_created = False

                    self[varName] = var
                    self.count += 1
                    logger.debug('AppChildren.load function, variable object created, varName = %s, var.id = %s', varName, var.id)

        if self._type == 'measures':
            self._df = _get_ms_pandas(self.parent.ws, self.app_handle)
            if len(self._df) == 0:
                logger.debug('AppChildren.load function, no measures found')
                self._loaded = True
                return True
            for msName in self._df['qMeta.title']:
                if pd.notna(msName):
                    ms = Measure(self, msName)
                    ms.app_handle = self.app_handle

                    row = self._df[self._df['qMeta.title'] == msName].iloc[0]
                    ms.id = row['qInfo.qId']
                    if 'qMeta.description' in self._df.columns: ms.description = row['qMeta.description']
                    if 'qData.measure.qDef' in self._df.columns: ms.definition = row['qData.measure.qDef']
                    if 'qData.measure.qLabel' in self._df.columns: ms.label = row['qData.measure.qLabel']
                    if 'qData.measure.qLabelExpression' in self._df.columns: ms.label_expression = row['qData.measure.qLabelExpression']
                    if 'qData.measure.qNumFormat.qFmt' in self._df.columns: ms.format = row['qData.measure.qNumFormat.qFmt']
                    if 'qData.measure.qNumFormat.qType' in self._df.columns: ms.format_type = row['qData.measure.qNumFormat.qType']
                    if 'qData.measure.qNumFormat.qnDec' in self._df.columns: ms.format_ndec = row['qData.measure.qNumFormat.qnDec']
                    if 'qData.measure.qNumFormat.qUseThou' in self._df.columns: ms.format_use_thou = row['qData.measure.qNumFormat.qUseThou']
                    if 'qData.measure.qNumFormat.qDec' in self._df.columns: ms.format_dec = row['qData.measure.qNumFormat.qDec']
                    if 'qData.measure.qNumFormat.qThou' in self._df.columns: ms.format_thou = row['qData.measure.qNumFormat.qThou']
                    if 'qData.measure.coloring.baseColor.color' in self._df.columns: ms.base_color = row['qData.measure.coloring.baseColor.color']
                    if 'qMeta.createdDate' in self._df.columns:
                        try: ms.created_date = dt.datetime.strptime(row['qMeta.createdDate'], '%Y-%m-%dT%H:%M:%S.%fZ')
                        except (ValueError, TypeError): pass
                    if 'qMeta.modifiedDate' in self._df.columns: 
                        try: ms.modified_date = dt.datetime.strptime(row['qMeta.modifiedDate'], '%Y-%m-%dT%H:%M:%S.%fZ')
                        except (ValueError, TypeError): pass

                    self[msName] = ms
                    self.count += 1
                    logger.debug('AppChildren.load function, measure object created, msName = %s, ms.id = %s', msName, ms.id)
                    
        if self._type == 'sheets':
            self._df = _get_sheet_pandas(self.parent.ws, self.app_handle)
            if len(self._df) == 0:
                logger.debug('AppChildren.load function, no sheets found')
                self._loaded = True
                return True
            for shName in self._df['qMeta.title']:
                if pd.notna(shName):
                    sh = Sheet(self, shName)
                    sh.app_handle = self.app_handle
                    
                    row = self._df[self._df['qMeta.title'] == shName].iloc[0]
                    sh.id = row['qInfo.qId']
                    if 'qMeta.description' in self._df.columns: sh.description = row['qMeta.description']
                    try: 
                        if 'qMeta.created_date' in self._df.columns: sh.created_date = dt.datetime.strptime(row['qMeta.createdDate'], '%Y-%m-%dT%H:%M:%S.%fZ')
                    except (ValueError, TypeError): pass
                    try:
                        if 'qMeta.modifiedDate' in self._df.columns: sh.modified_date = dt.datetime.strptime(row['qMeta.modifiedDate'], '%Y-%m-%dT%H:%M:%S.%fZ')
                    except (ValueError, TypeError): pass
                    if 'qMeta.published' in self._df.columns: sh.published = row['qMeta.published']
                    if 'qMeta.approved' in self._df.columns: sh.approved = row['qMeta.approved']
                    if 'qMeta.owner.id' in self._df.columns: sh.owner_id = row['qMeta.owner.id']
                    if 'qMeta.owner.name' in self._df.columns: sh.owner_name = row['qMeta.owner.name']

                    self[shName] = sh
                    self.count += 1
                    logger.debug('AppChildren.load function, sheet object created, shName = %s, sh.id = %s', shName, sh.id)
                
        if self._type == 'fields':
            self._df = _get_field_pandas(self.parent.ws, self.app_handle)
            if len(self._df) == 0:
                logger.debug('AppChildren.load function, no fields found')
                self._loaded = True
                return True
            for fName in self._df['qFields.qName']:
                if pd.notna(fName):
                    f = Field(fName)
                    f.app_handle = self.app_handle
                    
                    row = self._df[self._df['qFields.qName'] == fName].iloc[0]
                    if 'qName' in self._df.columns: f.table_name = row['qName']
                    if 'qFields.qInformationDensity' in self._df.columns: f.information_density = row['qFields.qInformationDensity']
                    if 'qFields.qnNonNulls' in self._df.columns: f.non_nulls = row['qFields.qnNonNulls']
                    if 'qFields.qnRows' in self._df.columns: f.rows_count = row['qFields.qnRows']
                    if 'qFields.qSubsetRatio' in self._df.columns: f.subset_ratio = row['qFields.qSubsetRatio']
                    if 'qFields.qnTotalDistinctValues' in self._df.columns: f.distinct_values_count = row['qFields.qnTotalDistinctValues']
                    if 'qFields.qnPresentDistinctValues' in self._df.columns: f.present_distinct_values = row['qFields.qnPresentDistinctValues']
                    if 'qFields.qKeyType' in self._df.columns: f.key_type = row['qFields.qKeyType']
                    if 'qFields.qTags' in self._df.columns: f.tags = row['qFields.qTags']

                    self[fName] = f
                    self.count += 1
                    logger.debug('AppChildren.load function, field object created, fName = %s', fName)
                
        if self._type == 'dimensions':
            self._df = _get_dim_pandas(self.parent.ws, self.app_handle)
            if len(self._df) == 0:
                logger.debug('AppChildren.load function, no dimensions found')
                self._loaded = True
                return True
            for dimName in self._df['qMeta.title']:
                if pd.notna(dimName):
                    dim = Dimension(self, dimName)
                    dim.app_handle = self.app_handle

                    row = self._df[self._df['qMeta.title'] == dimName].iloc[0]
                    dim.id = row['qInfo.qId']
                    dim.definition = row['qDimFieldDefs'] if isinstance(row['qDimFieldDefs'], list) else []
                    dim.label = row['qDimFieldLabels'] if isinstance(row['qDimFieldLabels'], list) else []
                    dim.base_color = row['qDimFieldBaseColor']
                    try: dim.created_date = dt.datetime.strptime(row['qMeta.createdDate'], '%Y-%m-%dT%H:%M:%S.%fZ')
                    except (ValueError, TypeError): pass
                    try: dim.modified_date = dt.datetime.strptime(row['qMeta.modifiedDate'], '%Y-%m-%dT%H:%M:%S.%fZ')
                    except (ValueError, TypeError): pass

                    self[dimName] = dim
                    self.count += 1
                    logger.debug('AppChildren.load function, dimension object created, dimName = %s, dim.id = %s', dimName, dim.id)

        if self._type == 'bookmarks':
            self._df = _get_bookmark_pandas(self.parent.ws, self.app_handle)
            if len(self._df) == 0:
                logger.debug('AppChildren.load function, no bookmarks found')
                self._loaded = True
                return True
            for bmName in self._df['qMeta.title']:
                if pd.notna(bmName):
                    bm = Bookmark(self, bmName)
                    bm.app_handle = self.app_handle

                    row = self._df[self._df['qMeta.title'] == bmName].iloc[0]
                    bm.id = row['qInfo.qId']
                    bm.owner_id = row['qMeta.owner.id']
                    bm.owner_user_id = row['qMeta.owner.userId']
                    bm.owner_name = row['qMeta.owner.name']
                    bm.state_data = row['qData.qBookmark.qStateData']
                    bm.description = row['qMeta.description']
                    bm.published = row['qMeta.published']
                    bm.approved = row['qMeta.approved']
                    try: bm.created_date = dt.datetime.strptime(row['qMeta.createdDate'], '%Y-%m-%dT%H:%M:%S.%fZ')
                    except (ValueError, TypeError): pass
                    try: bm.modified_date = dt.datetime.strptime(row['qMeta.modifiedDate'], '%Y-%m-%dT%H:%M:%S.%fZ')
                    except (ValueError, TypeError): pass

                    self[bmName] = bm
                    self.count += 1
                    logger.debug('AppChildren.load function, bookmark object created, bmName = %s, bm.id = %s', bmName, bm.id)

        self._loaded = True
        self._index = None
        return True


    def _load_index(self) -> dict:
        """
        Load a lightweight name->ID index without creating Python objects.
        Cached in ``self._index``; cleared by ``load()``.
        """
        if self._index is not None:
            return self._index
        self._index = _get_name_id_index(self.ws, self.app_handle, self._type)
        return self._index


    def get(self, name: str = None, id: str = None):
        """
        Fetch a single object by name or ID without loading the full collection.

        If the collection is already loaded, looks up the item in memory.
        Otherwise, queries the Engine API for just the requested object.

        For Variables by name: uses GetVariableByName (no list needed).
        For Measures/Dimensions/Sheets/Bookmarks by name: loads a lightweight
        name->ID index, then fetches the individual object by ID.
        For any type by ID: direct Engine API call.

        The fetched object is cached in ``self.children`` for subsequent access.

        Args:
            name (str, optional): name of the object
            id (str, optional): Qlik Sense internal ID

        Returns:
            The object if found, None otherwise.
        """
        from qsea.objects import Variable, Measure, Dimension, Sheet, Bookmark

        if name is None and id is None:
            raise ValueError('Either name or id must be provided')

        if self._loaded:
            if name is not None:
                return self.children.get(name)
            for child in self.children.values():
                if getattr(child, 'id', None) == id:
                    return child
            return None

        logger.debug('AppChildren.get started, type=%s, name=%s, id=%s', self._type, name, id)

        if self._type == 'variables':
            return self._get_single_variable(name, id, Variable)
        if self._type == 'measures':
            return self._get_single_measure(name, id, Measure)
        if self._type == 'dimensions':
            return self._get_single_dimension(name, id, Dimension)
        if self._type == 'sheets':
            return self._get_single_sheet(name, id, Sheet)
        if self._type == 'bookmarks':
            return self._get_single_bookmark(name, id, Bookmark)

        return None


    def _get_single_variable(self, name, obj_id, Variable):
        if name is not None:
            layout = _get_single_variable_func(self.ws, self.app_handle, name)
        else:
            layout = _get_single_variable_by_id_func(self.ws, self.app_handle, obj_id)
        if layout is None:
            return None
        var = Variable._from_layout(self, layout)
        self.children[var.name] = var
        self.count = len(self.children)
        return var

    def _get_single_measure(self, name, obj_id, Measure):
        if obj_id is None:
            idx = self._load_index()
            obj_id = idx.get(name)
            if obj_id is None:
                return None
        props = _get_single_measure_func(self.ws, self.app_handle, obj_id)
        if props is None:
            return None
        ms = Measure._from_properties(self, props)
        self.children[ms.name] = ms
        self.count = len(self.children)
        return ms

    def _get_single_dimension(self, name, obj_id, Dimension):
        if obj_id is None:
            idx = self._load_index()
            obj_id = idx.get(name)
            if obj_id is None:
                return None
        props = _get_single_dimension_func(self.ws, self.app_handle, obj_id)
        if props is None:
            return None
        dim = Dimension._from_properties(self, props)
        self.children[dim.name] = dim
        self.count = len(self.children)
        return dim

    def _get_single_sheet(self, name, obj_id, Sheet):
        if obj_id is None:
            idx = self._load_index()
            obj_id = idx.get(name)
            if obj_id is None:
                return None
        layout = _get_single_sheet_func(self.ws, self.app_handle, obj_id)
        if layout is None:
            return None
        sh = Sheet._from_layout(self, layout)
        self.children[sh.name] = sh
        self.count = len(self.children)
        return sh

    def _get_single_bookmark(self, name, obj_id, Bookmark):
        if obj_id is None:
            idx = self._load_index()
            obj_id = idx.get(name)
            if obj_id is None:
                return None
        layout = _get_single_bookmark_func(self.ws, self.app_handle, obj_id)
        if layout is None:
            return None
        bm = Bookmark._from_layout(self, layout)
        self.children[bm.name] = bm
        self.count = len(self.children)
        return bm

    
    def add(self, name: str = '', definition: str = '', description: str = '', label: str = '', label_expression: str = '', format_type: str = 'U', \
                           format_ndec: int = 10, format_use_thou: int = 0, format_dec: str = ',', format_thou: str = '' \
                            , base_color = '', source = None) -> str:
        """
        Adds a new object to the app; depending on the type of the AppChildren object, the object will be a variable, a measure, or a dimension.

        Args:
            name (str): Name of the object to be created.
            definition (str): Definition of the object to be created.
            description (str, optional): Description of the object to be created. Defaults to ''.
            label (str, optional): Label of the object to be created. Defaults to ''.
            label_expression (str, optional): Label expression of the object to be created. Defaults to ''.
            format_type (str, optional): Format type of the object to be created. Defaults to 'U'.
                'U' for auto
                'F' for number
                'M' for money
                'D' for date
                'IV' for duration
                'R' for other
            format_ndec (int, optional): Number of decimals of the object to be created. Defaults to 10.
            format_use_thou (int, optional): Use thousands separator of the object to be created. Defaults to 0.
            format_dec (str, optional): Decimal separator of the object to be created. Defaults to ','.
            format_thou (str, optional): Thousands separator of the object to be created. Defaults to ''.
            base_color (str, optional): Base color (hex) of the measure to be created. Defaults to ''.
            source (variable, measure or dimension, optional): Source object to be copied. Defaults to None.

        Returns:
            str: obejct_id if the object was created successfully, None otherwise.
        """
        from qsea.objects import Variable, Measure, Dimension, Sheet
        
        logger.debug('AppChildren.add function started, type = %s, name = %s, definition = %s, description = %s, label = %s, source = %s', \
                     self._type, name, definition, description, label, source)
        
        if source is None and (name == '' or definition == '') and self._type != 'sheets':
            logger.error('AppChildren.add function, either source or both name and definition are required')
            return None
        
        if source is not None and not isinstance(source, (Variable, Measure, Dimension, Sheet)):
            logger.error('AppChildren.add function, source must be a Variable, Measure, Dimension or Sheet object, %s provided', type(source))
            return None

        if source is not None:
            if (isinstance(source, Variable) and self._type != 'variables') or \
                (isinstance(source, Measure) and self._type != 'measures') or \
                (isinstance(source, Dimension) and self._type != 'dimensions'):
                logger.error('AppChildren.add function, source type does not match AppChildren type')
                return None
            
        if source is not None and self._type == 'sheets':
            logger.error('AppChildren.add function, source is not supported for sheets')
            return None

        if self._type == 'variables':
            if source is not None:
                name = source.name
                definition = source.definition
                description = source.description

            query_result = query(self.parent.ws, {
                "jsonrpc": "2.0",
                "id": _next_rpc_id(),
                "method": "CreateVariableEx",
                "handle": self.app_handle,
                "params": [
                    {
                        "qInfo": {
                            "qType": "variable"
                        },
                    "qName": name,
                    "qComment": description,
                    "qDefinition": definition
                    }
                ]
            })
            
            if 'error' in query_result and 'parameter' in query_result['error'] \
                    and query_result['error']['parameter'] == 'Variable already exists':
                logger.error('Variable already exists: %s', name)
                return None
            
            var = Variable(self, name)
            var.app_handle = self.app_handle

            self.df = _get_var_pandas(self.ws, self.app_handle)
            row = self.df[self.df['qName'] == name].iloc[0]
            var.id = row['qInfo.qId']
            if 'qDefinition' in self.df.columns: var.definition = row['qDefinition']
            if 'qDescription' in self.df.columns: var.description = row['qDescription']
            if 'qIsScriptCreated' in self.df.columns: var.script_created = row['qIsScriptCreated']
            if pd.isna(var.script_created): var.script_created = False

            self[name] = var
            self.count += 1
            logger.info('Variable created: %s, definition: %s, description: %s', name, definition, description)
            return query_result['result']['qInfo']['qId']
        
        if self._type == 'measures':
            if source is not None:
                mprop = source.get_layout()
                if 'result' not in mprop or 'qLayout' not in mprop['result'] or 'qMeasure' not in mprop['result']['qLayout']:
                    logger.error('AppChildren.add function, source layout is not valid')
                    return None
                tmprop = mprop['result']['qLayout']['qMeasure']
                
                if source.label_expression != source.label_expression: le = ''
                else: le = source.label_expression
                tmprop['qLabelExpression'] = le        
                
                t = {
                    "handle": self.app_handle,
                    "method": "CreateMeasure",
                    "params": {
                        "qProp": {
                            "qInfo": {
                                "qType": "measure"
                            },
                            "qMeasure": tmprop,
                            "qMetaDef": {
                                "title": source.name,
                                "description": source.description
                                                }
                        }
                    }
                }
                name = source.name

            else:
                t = {
                    "handle": self.app_handle,
                    "method": "CreateMeasure",
                    "params": {
                        "qProp": {
                            "qInfo": {
                                "qType": "measure"
                            },
                            "qMeasure": {
                                "qLabel": label,
                                "isCustomFormatted": True,
                                "numFormatFromTemplate": False,
                                "qNumFormat": {
                                                    "qType": format_type,
                                                    "qnDec": format_ndec,
                                                    'qUseThou': format_use_thou,
                                                    "qDec": format_dec,
                                                    'qThou': format_thou
                                                        },
                                "coloring": {"baseColor": {"color": base_color,
                                    'index': 1}},
                                "qLabelExpression": label_expression,
                                "qDef": definition,
                                "qGrouping": 0,
                                "qExpressions": [
                                    ""
                                ],
                                "qActiveExpression": 0
                            },
                            "qMetaDef": {
                                "title": name,
                                "description": description
                                                }
                        }
                    }
                }
            query_result = query(self.parent.ws, t)
            
            if 'result' in query_result and 'qReturn' in query_result['result'] and 'qHandle' in query_result['result']['qReturn'] \
                and query_result['result']['qReturn']['qHandle'] > 0:

                ms = Measure(self, name)
                ms.app_handle = self.app_handle

                self.df = _get_ms_pandas(self.ws, self.app_handle)
                row = self.df[self.df['qMeta.title'] == name].iloc[0]
                ms.id = row['qInfo.qId']
                if 'qMeta.description' in self.df.columns: ms.description = row['qMeta.description']
                if 'qData.measure.qDef' in self.df.columns: ms.definition = row['qData.measure.qDef']
                if 'qData.measure.qLabel' in self.df.columns: ms.label = row['qData.measure.qLabel']
                if 'qData.measure.qLabelExpression' in self.df.columns: ms.label_expression = row['qData.measure.qLabelExpression']
                if 'qData.measure.qNumFormat.qFmt' in self.df.columns: ms.format = row['qData.measure.qNumFormat.qFmt']
                if 'qData.measure.qNumFormat.qType' in self.df.columns: ms.format_type = row['qData.measure.qNumFormat.qType']
                if 'qData.measure.qNumFormat.qnDec' in self.df.columns: ms.format_ndec = row['qData.measure.qNumFormat.qnDec']
                if 'qData.measure.qNumFormat.qUseThou' in self.df.columns: ms.format_use_thou = row['qData.measure.qNumFormat.qUseThou']
                if 'qData.measure.qNumFormat.qDec' in self.df.columns: ms.format_dec = row['qData.measure.qNumFormat.qDec']
                if 'qData.measure.qNumFormat.qThou' in self.df.columns: ms.format_thou = row['qData.measure.qNumFormat.qThou']
                if 'qData.measure.coloring.baseColor.color' in self.df.columns: ms.base_color = row['qData.measure.coloring.baseColor.color']
                try: ms.created_date = dt.datetime.strptime(row['qMeta.createdDate'], '%Y-%m-%dT%H:%M:%S.%fZ')
                except (ValueError, TypeError): pass
                try: ms.modified_date = dt.datetime.strptime(row['qMeta.modifiedDate'], '%Y-%m-%dT%H:%M:%S.%fZ')
                except (ValueError, TypeError): pass

                self[name] = ms
                self.count += 1
                logger.info('Measure created: %s, definition: %s, label: %s', name, ms.definition, ms.label)
                return query_result['result']['qInfo']['qId']
            else: 
                logger.error('Failed to create measure: %s', name)
                return None
        
        if self._type == 'dimensions':
            if source is not None:
                mprop = source.get_layout()
                if 'result' not in mprop or 'qLayout' not in mprop['result'] or 'qDim' not in mprop['result']['qLayout']:
                    logger.error('AppChildren.add function, source layout is not valid')
                    return None
                tmprop = mprop['result']['qLayout']['qDim']
                if 'qDimInfos' in mprop['result']['qLayout']:
                    tmprop_infos = mprop['result']['qLayout']['qDimInfos']
                else:
                    tmprop_infos = []

                t = {
                    "handle": self.app_handle,
                    "method": "CreateDimension",
                    "params": [{
                            "qInfo": {"qType": "dimension"},
                            "qDim": tmprop,
                            "qDimInfos": tmprop_infos,
                            "qMetaDef": {"title": source.name, "description": source.description, "tags": []}
                            }]
                    }
                name = source.name

            else:
                if isinstance(definition, str): definition = [definition]
                if isinstance(label, str): label = [label]
                t = {
                    "handle": self.app_handle,
                    "method": "CreateDimension",
                    "params": [{
                            "qInfo": {"qType": "dimension"},
                            "qDim": {
                                "qGrouping": "N",
                                "qFieldDefs": definition,
                                "qFieldLabels": label,
                                "coloring": {'baseColor': {'color': base_color}}
                                    },
                            "qMetaDef": {"title": name, "description": description, "tags": []}
                            }]
                    }

            query_result = query(self.parent.ws, t)
            
            if 'result' in query_result and 'qReturn' in query_result['result'] \
                    and 'qHandle' in query_result['result']['qReturn'] \
                    and query_result['result']['qReturn']['qHandle'] > 0:

                dim = Dimension(self, name)
                dim.app_handle = self.app_handle
                dim.handle = query_result['result']['qReturn']['qHandle']

                prop_result = query(self.parent.ws, {
                    "jsonrpc": "2.0",
                    "id": _next_rpc_id(),
                    "method": "GetProperties",
                    "handle": dim.handle,
                    "params": {}
                    })

                self.df = _get_dim_pandas(self.ws, self.app_handle)
                dim.id = prop_result['result']['qProp']['qInfo']['qId']
                self.df = pd.concat([self.df, pd.DataFrame({col: [dim.id] if col == 'qInfo.qId' else [None] for col in self.df.columns})])
                self.df.reset_index(inplace=True)
                row_label = self.df.index[self.df['qInfo.qId'] == dim.id].tolist()[0]
                self.df.at[row_label, 'qMeta.title'] = dim.name

                if _find_key('qFieldDefs', prop_result): 
                    dim.definition = prop_result['result']['qProp']['qDim']['qFieldDefs']
                    self.df.at[row_label, 'qDimFieldDefs'] = dim.definition
                if _find_key('qFieldLabels', prop_result): 
                    dim.label = prop_result['result']['qProp']['qDim']['qFieldLabels']
                    self.df.at[row_label, 'qDimFieldLabels'] = dim.label
                if _find_key('coloring', prop_result):
                    dim.base_color = prop_result['result']['qProp']['qDim']['coloring']['baseColor']['color']
                    self.df.at[row_label, 'qDimFieldBaseColor'] = dim.base_color

                self[name] = dim
                self.count += 1
                logger.info('Dimension created: %s, definition: %s, label: %s', name, definition, label)
                return query_result['result']['qInfo']['qId']
            else: 
                logger.error('Failed to create dimension: %s', name)
                return None
            
        if self._type == 'sheets':
            if self.parent.sheets.count == 0: self.parent.sheets.load()
            if name in self.parent.sheets.df['qMeta.title'].tolist():
                logger.error('Sheet.copy function, sheet with the same name already exists in the app, name = %s, target_app = %s', name, self.parent.name)
                return None
            
            t = {
                "jsonrpc": "2.0",
                "id": _next_rpc_id(),
                "method": "CreateObject",
                "handle": self.parent.handle,
                "params": [
                    {
                    "title": name,
                    "description": description,
                    "qInfo": {
                        "qType": "sheet"
                    },
                    "qMetaDef": {"title": name, "description": description},
                    "qChildListDef": {
                        "qData": {
                        "title": "/title",
                        "description": "/description",
                        "meta": "/meta",
                        "order": "/order",
                        "type": "/qInfo/qType",
                        "id": "/qInfo/qId",
                        "lb": "/qListObjectDef",
                        "hc": "/qHyperCubeDef"
                        }
                    },
                    "cells": []
                    }
                ]
                }
            
            query_result = query(self.parent.ws, t)
            if not 'result' in query_result or not 'qInfo' in query_result['result'] or not 'qId' in query_result['result']['qInfo']:
                logger.error('Sheet.copy function, creating a new sheet failed, name = %s', self.name)
                return None
            
            sh = Sheet(self, name)
            sh.app_handle = self.app_handle

            self.df = _get_sheet_pandas(self.ws, self.app_handle)
            row = self.df[self.df['qMeta.title'] == name].iloc[0]
            sh.id = row['qInfo.qId']
            if 'qMeta.description' in self.df.columns: sh.description = row['qMeta.description']
            try: 
                if 'qMeta.created_date' in self.df.columns: sh.created_date = dt.datetime.strptime(row['qMeta.createdDate'], '%Y-%m-%dT%H:%M:%S.%fZ')
            except (ValueError, TypeError): pass
            try: 
                if 'qMeta.modifiedDate' in self.df.columns: sh.modified_date = dt.datetime.strptime(row['qMeta.modifiedDate'], '%Y-%m-%dT%H:%M:%S.%fZ')
            except (ValueError, TypeError): pass
            if 'qMeta.published' in self.df.columns: sh.published = row['qMeta.published']
            if 'qMeta.approved' in self.df.columns: sh.approved = row['qMeta.approved']
            if 'qMeta.owner.id' in self.df.columns: sh.owner_id = row['qMeta.owner.id']
            if 'qMeta.owner.name' in self.df.columns: sh.owner_name = row['qMeta.owner.name']

            self[name] = sh
            self.count += 1

            logger.info('Sheet created: %s', name)
            return query_result['result']['qInfo']['qId']
        
        if self._type not in ['measures', 'dimensions', 'variables', 'sheets']:
            logger.error('Creation of %s is not supported', self._type)
            return None
