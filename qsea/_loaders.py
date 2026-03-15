import pandas as pd

from qsea._config import logger
from qsea._engine import query, _get_layout, _get_properties, _next_rpc_id
from qsea._selections import _destroy_session_object


def _get_app_list(ws) -> pd.DataFrame:
    """
    Returns a dataframe with all apps and their properties

    Args:
        ws (websocket): websocket connection

    Returns:
        dataframe: dataframe with all apps and their properties
    """
    logger.debug('_get_app_list function started')

    query_result = query(ws, {
        "handle": -1,
        "method": "GetDocList",
        "params": [],
        "outKey": -1,
        "id": _next_rpc_id()
        })
    
    if query_result is None or 'result' not in query_result or 'qDocList' not in query_result['result']:
        logger.error('_get_app_list failed: unexpected response')
        return pd.DataFrame()

    df = pd.json_normalize(query_result['result']['qDocList'])
    logger.debug('_get_app_list function completed, len(df): %s', len(df))
    return df


def _get_var_pandas(ws, app_handle: int) -> pd.DataFrame:
    """
    Returns a dataframe with all app variables and their properties

    Args:
        ws (websocket): websocket connection
        app_handle (int): App handle

    Returns:
        dataframe: dataframe with all app variables and their properties
    """ 

    logger.debug('_get_var_pandas function started, app_handle = %s', app_handle)
    query_result = query(ws, {
          "jsonrpc": "2.0",
          "id": _next_rpc_id(),
          "method": "CreateSessionObject",
          "handle": app_handle,
          "params": [
            {
              "qInfo": {
                "qId": "VL01",
                "qType": "VariableList"
              },      
              "qVariableListDef": {
                "qType": "variable"
              }
            }
          ]
        }
    )
    if query_result is None:
        raise ValueError('Could not get VariableList handle: no response from Engine')
    if 'error' in query_result:
        raise ValueError(f"Could not get VariableList handle: {query_result['error'].get('message', query_result['error'])}")
    if 'result' not in query_result or 'qReturn' not in query_result['result'] or \
        'qHandle' not in query_result['result']['qReturn']:
        raise ValueError(f'Could not get VariableList handle: unexpected response: {query_result}')

    list_handle = query_result['result']['qReturn']['qHandle']
    
    layout = _get_layout(ws, list_handle)
    if layout is None or 'result' not in layout or 'qLayout' not in layout['result'] \
            or 'qVariableList' not in layout['result']['qLayout'] \
            or 'qItems' not in layout['result']['qLayout']['qVariableList']:
        raise ValueError(f'VariableList layout structure is not as expected: {layout}')
    
    df = pd.json_normalize(layout['result']['qLayout']['qVariableList']['qItems'])
    _destroy_session_object(ws, app_handle, "VL01")
    logger.debug('_get_var_pandas function completed, len(df): %s', len(df))
    return df


def _get_ms_pandas(ws, app_handle: int) -> pd.DataFrame:
    """
    Returns a dataframe with all app master measures and their properties

    Args:
        ws (websocket): websocket connection
        app_handle (int): App handle

    Returns:
        dataframe: dataframe with all app master measures and their properties
    """

    logger.debug('_get_ms_pandas function started, app_handle = %s', app_handle)
    query_result = query(ws, {
          "jsonrpc": "2.0",
          "id": _next_rpc_id(),
          "method": "CreateSessionObject",
          "handle": app_handle,
          "params": [
            {
              "qInfo": {
                "qId": "ML01",
                "qType": "MeasureList"
              },      
              "qMeasureListDef": {
                "qType": "measure",
                "qData": {
                    "title": "/title",
                    "tags": "/tags",
                    "measure": "/qMeasure"
                    }
              }
            }
          ]
        }
    )

    if query_result is None:
        raise ValueError('Could not get MeasureList handle: no response from Engine')
    if 'error' in query_result:
        raise ValueError(f"Could not get MeasureList handle: {query_result['error'].get('message', query_result['error'])}")
    if 'result' not in query_result or 'qReturn' not in query_result['result'] \
            or 'qHandle' not in query_result['result']['qReturn']:
        raise ValueError(f'Could not get MeasureList handle: unexpected response: {query_result}')

    list_handle = query_result['result']['qReturn']['qHandle']

    layout = _get_layout(ws, list_handle)
    if layout is None or 'result' not in layout or 'qLayout' not in layout['result'] \
            or 'qMeasureList' not in layout['result']['qLayout'] \
            or 'qItems' not in layout['result']['qLayout']['qMeasureList']:
        raise ValueError(f'MeasureList layout structure is not as expected: {layout}')
    
    df = pd.json_normalize(layout['result']['qLayout']['qMeasureList']['qItems'])
    _destroy_session_object(ws, app_handle, "ML01")
    logger.debug('_get_ms_pandas function completed, len(df): %s', len(df))
    return df


def _get_sheet_pandas(ws, app_handle: int) -> pd.DataFrame:
    """
    Returns a dataframe with all app sheets and their properties

    Args:
        ws (websocket): websocket connection
        app_handle (int): App handle

    Returns:
        dataframe: dataframe with all app sheets and their properties
    """
    
    logger.debug('_get_sheet_pandas function started, app_handle = %s', app_handle)
    query_result = query(ws, {
      "jsonrpc": "2.0",
      "id": _next_rpc_id(),
      "method": "CreateSessionObject",
      "handle": app_handle,
      "params": [
        {
          "qInfo": {
            "qId": "",
            "qType": "SessionLists"
          },
          "qAppObjectListDef": {
            "qType": "sheet",
            "qData": {
              "id": "/qInfo/qId"
            }
          }
        }
      ]
    })
    
    if query_result is None or 'result' not in query_result or 'qReturn' not in query_result['result'] \
            or 'qHandle' not in query_result['result']['qReturn']:
        raise ValueError('Could not get SheetList handle')

    list_handle = query_result['result']['qReturn']['qHandle']
    
    layout = _get_layout(ws, list_handle)
    if 'result' not in layout or 'qLayout' not in layout['result'] or 'qAppObjectList' not in layout['result']['qLayout'] or \
        'qItems' not in layout['result']['qLayout']['qAppObjectList']:
        raise ValueError('Layout structure is not as expected.')
    
    df = pd.json_normalize(layout['result']['qLayout']['qAppObjectList']['qItems'])
    logger.debug('_get_sheet_pandas function completed, len(df): %s', len(df))
    return df


def _get_field_pandas(ws, app_handle: int) -> pd.DataFrame:
    """
    Returns a dataframe with all app fields and their properties

    Args:
        ws (websocket): websocket connection
        app_handle (int): App handle

    Returns:
        dataframe: dataframe with all app fields and their properties
    """

    logger.debug('_get_field_pandas function started, app_handle = %s', app_handle)

    query_result = query(ws, {
      "jsonrpc": "2.0",
      "id": _next_rpc_id(),
      "method": "GetTablesAndKeys",
      "handle": app_handle,
      "params": [
        {
          "qcx": 1000,
          "qcy": 1000
        },
        {
          "qcx": 0,
          "qcy": 0
        },
        30,
        True,
        False
      ]
    })
    

    if 'result' not in query_result or 'qtr' not in query_result['result']:
        raise ValueError('Query response structure is not as expected.')
    
    df = pd.json_normalize(query_result['result']['qtr'])
    qFields = df['qFields'].explode().apply(pd.Series)
    qFields.rename(columns={col:f'qFields.{col}' for col in qFields.columns}, inplace=True)
    cols = [col for col in df.columns if col not in ['qFields.records']]
    pdf = df[cols].join(qFields)
    
    logger.debug('_get_field_pandas function completed, len(df): %s', len(pdf))
    return pdf


def _get_dim_pandas(ws, app_handle: int) -> pd.DataFrame:
    """
    Returns a dataframe with all app dimensions and their properties

    Args:
        ws (websocket): websocket connection
        app_handle (int): App handle

    Returns:
        dataframe: dataframe with all app dimensions and their properties
    """
    
    logger.debug('_get_dim_pandas function started, app_handle = %s', app_handle)
    
    query_result = query(ws, {
          "jsonrpc": "2.0",
          "id": _next_rpc_id(),
          "method": "CreateSessionObject",
          "handle": app_handle,
          "params": [
            {
              "qInfo": {
                "qId": "ML01",
                "qType": "DimensionList"
              },      
              "qDimensionListDef": {
                "qType": "dimension",
                "qData": {
                    "title": "/title",
                    "tags": "/tags",
                    "dimension": "/qDimension"
                    }
              }
            }
          ]
        }
    )

    if query_result is None:
        raise ValueError('Could not get DimensionList handle: no response from Engine')
    if 'error' in query_result:
        raise ValueError(f"Could not get DimensionList handle: {query_result['error'].get('message', query_result['error'])}")
    if 'result' not in query_result or 'qReturn' not in query_result['result'] or 'qHandle' not in query_result['result']['qReturn']:
        raise ValueError(f'Could not get DimensionList handle: unexpected response: {query_result}')

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

    listHandle = query_result['result']['qReturn']['qHandle']
    df = pd.json_normalize(_get_layout(ws, listHandle)['result']['qLayout']['qDimensionList']['qItems'])
    df['qDimFieldDefs'] = pd.Series([None] * len(df), dtype='object')
    df['qDimFieldGrouping'] = pd.Series(['Unknown'] * len(df), dtype='object')
    df['qDimFieldLabels'] = pd.Series([None] * len(df), dtype='object')
    df['qDimFieldBaseColor'] = pd.Series(['Unknown'] * len(df), dtype='object')

    for i in range(len(df)):

        dimhandle = query(ws, {
            "jsonrpc": "2.0",
            "id": _next_rpc_id(),
            "method": "GetDimension",
            "handle": app_handle,
            "params": [df['qInfo.qId'][i]]
        })['result']['qReturn']['qHandle']

        query_result = query(ws, {
            "jsonrpc": "2.0",
            "id": _next_rpc_id(),
            "method": "GetProperties",
            "handle": dimhandle,
            "params": {}
            })
        
        dim_props = query_result['result']['qProp']['qDim']
        df.at[i, 'qDimFieldDefs'] = _normalize_dim_list(dim_props.get('qFieldDefs'))
        df.at[i, 'qDimFieldGrouping'] = dim_props.get('qGrouping', 'Unknown')
        df.at[i, 'qDimFieldLabels'] = _normalize_dim_list(dim_props.get('qFieldLabels'))
        if 'coloring' in dim_props and 'baseColor' in dim_props['coloring'] \
            and 'color' in dim_props['coloring']['baseColor']:
            df.at[i, 'qDimFieldBaseColor'] = dim_props['coloring']['baseColor']['color']

    _destroy_session_object(ws, app_handle, "ML01")
    logger.debug('_get_dim_pandas function completed, len(df): %s', len(df))
    return df


def _get_bookmark_pandas(ws, app_handle: int) -> pd.DataFrame:
    """
    Returns a dataframe with all app bookmarks and their properties

    Args:
        ws (websocket): websocket connection
        app_handle (int): App handle

    Returns:
        dataframe: dataframe with all app bookmarks and their properties
    """

    logger.debug('_get_bookmark_pandas function started, app_handle = %s', app_handle)

    query_result = query(ws, {
        "jsonrpc": "2.0",
        "id": _next_rpc_id(),
        "method": "CreateSessionObject",
        "handle": app_handle,
        "params": [
            {
            "qInfo": {
                "qId": "BL01",
                "qType": "BookmarkList"
            },
            "qBookmarkListDef": {
                "qType": "bookmark"
            }
            }
        ]
        }
    )

    if query_result is None:
        raise ValueError('Could not get BookmarkList handle: no response from Engine')
    if 'error' in query_result:
        raise ValueError(f"Could not get BookmarkList handle: {query_result['error'].get('message', query_result['error'])}")
    if 'result' not in query_result or 'qReturn' not in query_result['result'] \
            or 'qHandle' not in query_result['result']['qReturn']:
        raise ValueError(f'Could not get BookmarkList handle: unexpected response: {query_result}')

    list_handle = query_result['result']['qReturn']['qHandle']

    layout = _get_layout(ws, list_handle)
    if layout is None or 'result' not in layout or 'qLayout' not in layout['result'] \
            or 'qInfo' not in layout['result']['qLayout'] \
            or 'qItems' not in layout['result']['qLayout']['qBookmarkList']:
        raise ValueError(f'BookmarkList layout structure is not as expected: {layout}')
    
    df = pd.json_normalize(layout['result']['qLayout']['qBookmarkList']['qItems'])
    _destroy_session_object(ws, app_handle, "BL01")

    logger.debug('_get_bookmark_pandas function completed, len(df): %s', len(df))
    return df


def _get_name_id_index(ws, app_handle: int, collection_type: str) -> dict:
    """
    Load a lightweight name->ID mapping from a session list without
    fetching per-item properties.  Much cheaper than a full load for
    dimensions (avoids N*2 extra API calls).

    Args:
        ws: websocket connection
        app_handle (int): App handle
        collection_type (str): one of 'variables', 'measures', 'dimensions',
                               'sheets', 'bookmarks'

    Returns:
        dict: {name: qlik_id, ...}
    """
    logger.debug('_get_name_id_index started, type=%s', collection_type)

    if collection_type == 'variables':
        df = _get_var_pandas(ws, app_handle)
        if len(df) == 0:
            return {}
        return dict(zip(df['qName'], df['qInfo.qId']))

    if collection_type == 'measures':
        df = _get_ms_pandas(ws, app_handle)
        if len(df) == 0:
            return {}
        return dict(zip(df['qMeta.title'], df['qInfo.qId']))

    if collection_type == 'dimensions':
        qr = query(ws, {
            "jsonrpc": "2.0", "id": _next_rpc_id(),
            "method": "CreateSessionObject", "handle": app_handle,
            "params": [{"qInfo": {"qId": "DL_IDX", "qType": "DimensionList"},
                        "qDimensionListDef": {"qType": "dimension",
                                              "qData": {"title": "/title"}}}]
        })
        if qr is None or 'result' not in qr:
            return {}
        lh = qr['result']['qReturn']['qHandle']
        layout = _get_layout(ws, lh)
        _destroy_session_object(ws, app_handle, "DL_IDX")
        items = layout['result']['qLayout']['qDimensionList'].get('qItems', [])
        return {item['qMeta']['title']: item['qInfo']['qId'] for item in items
                if item.get('qMeta', {}).get('title')}

    if collection_type == 'sheets':
        df = _get_sheet_pandas(ws, app_handle)
        if len(df) == 0:
            return {}
        return dict(zip(df['qMeta.title'], df['qInfo.qId']))

    if collection_type == 'bookmarks':
        df = _get_bookmark_pandas(ws, app_handle)
        if len(df) == 0:
            return {}
        return dict(zip(df['qMeta.title'], df['qInfo.qId']))

    return {}


def _get_single_variable(ws, app_handle: int, name: str) -> dict:
    """
    Fetch a single variable by name using GetVariableByName + GetProperties.

    Returns:
        dict with variable properties, or None on failure.
    """
    logger.debug('_get_single_variable started, name=%s', name)
    result = query(ws, {
        "jsonrpc": "2.0", "id": _next_rpc_id(),
        "method": "GetVariableByName",
        "handle": app_handle,
        "params": [name]
    })
    if result is None or 'result' not in result or 'qReturn' not in result['result']:
        logger.warning('_get_single_variable: variable not found: %s', name)
        return None
    handle = result['result']['qReturn']['qHandle']
    props = _get_properties(ws, handle)
    if props is None or 'result' not in props:
        return None
    return props['result']['qProp']


def _get_single_variable_by_id(ws, app_handle: int, var_id: str) -> dict:
    """
    Fetch a single variable by ID using GetVariableById + GetProperties.

    Returns:
        dict with variable properties, or None on failure.
    """
    logger.debug('_get_single_variable_by_id started, id=%s', var_id)
    result = query(ws, {
        "jsonrpc": "2.0", "id": _next_rpc_id(),
        "method": "GetVariableById",
        "handle": app_handle,
        "params": [var_id]
    })
    if result is None or 'result' not in result or 'qReturn' not in result['result']:
        logger.warning('_get_single_variable_by_id: variable not found: %s', var_id)
        return None
    handle = result['result']['qReturn']['qHandle']
    props = _get_properties(ws, handle)
    if props is None or 'result' not in props:
        return None
    return props['result']['qProp']


def _get_single_measure(ws, app_handle: int, measure_id: str) -> dict:
    """
    Fetch a single measure by ID using GetMeasure + GetProperties.

    Returns:
        dict with measure properties (qProp), or None on failure.
    """
    logger.debug('_get_single_measure started, id=%s', measure_id)
    result = query(ws, {
        "jsonrpc": "2.0", "id": _next_rpc_id(),
        "method": "GetMeasure",
        "handle": app_handle,
        "params": [measure_id]
    })
    if result is None or 'result' not in result or 'qReturn' not in result['result']:
        logger.warning('_get_single_measure: measure not found: %s', measure_id)
        return None
    handle = result['result']['qReturn']['qHandle']
    props = _get_properties(ws, handle)
    if props is None or 'result' not in props:
        return None
    return props['result']['qProp']


def _get_single_dimension(ws, app_handle: int, dim_id: str) -> dict:
    """
    Fetch a single dimension by ID using GetDimension + GetProperties.

    Returns:
        dict with dimension properties (qProp), or None on failure.
    """
    logger.debug('_get_single_dimension started, id=%s', dim_id)
    result = query(ws, {
        "jsonrpc": "2.0", "id": _next_rpc_id(),
        "method": "GetDimension",
        "handle": app_handle,
        "params": [dim_id]
    })
    if result is None or 'result' not in result or 'qReturn' not in result['result']:
        logger.warning('_get_single_dimension: dimension not found: %s', dim_id)
        return None
    handle = result['result']['qReturn']['qHandle']
    props = _get_properties(ws, handle)
    if props is None or 'result' not in props:
        return None
    return props['result']['qProp']


def _get_single_sheet(ws, app_handle: int, sheet_id: str) -> dict:
    """
    Fetch a single sheet by ID using GetObject + GetLayout.

    Returns:
        dict with sheet layout data, or None on failure.
    """
    logger.debug('_get_single_sheet started, id=%s', sheet_id)
    result = query(ws, {
        "jsonrpc": "2.0", "id": _next_rpc_id(),
        "method": "GetObject",
        "handle": app_handle,
        "params": [sheet_id]
    })
    if result is None or 'result' not in result or 'qReturn' not in result['result']:
        logger.warning('_get_single_sheet: sheet not found: %s', sheet_id)
        return None
    handle = result['result']['qReturn']['qHandle']
    layout = _get_layout(ws, handle)
    if layout is None or 'result' not in layout:
        return None
    return layout['result']['qLayout']


def _get_single_bookmark(ws, app_handle: int, bookmark_id: str) -> dict:
    """
    Fetch a single bookmark by ID using GetBookmark + GetLayout.

    Returns:
        dict with bookmark layout data, or None on failure.
    """
    logger.debug('_get_single_bookmark started, id=%s', bookmark_id)
    result = query(ws, {
        "jsonrpc": "2.0", "id": _next_rpc_id(),
        "method": "GetBookmark",
        "handle": app_handle,
        "params": [bookmark_id]
    })
    if result is None or 'result' not in result or 'qReturn' not in result['result']:
        logger.warning('_get_single_bookmark: bookmark not found: %s', bookmark_id)
        return None
    handle = result['result']['qReturn']['qHandle']
    layout = _get_layout(ws, handle)
    if layout is None or 'result' not in layout:
        return None
    return layout['result']['qLayout']


def _get_sheet_objects_pandas(ws, sheet_handle: int) -> pd.DataFrame:
    """
    Returns a dataframe with all objects on the sheet and their properties

    Args:
        ws (websocket): websocket connection
        sheet_handle (int): Sheet handle

    Returns:
        dataframe: dataframe with all objects on the sheet and their properties
    """
    logger.debug('_get_sheet_objects_pandas function started, sheet_handle = %s', sheet_handle)

    sheet_layout = _get_layout(ws, sheet_handle)
    if 'result' not in sheet_layout or 'qLayout' not in sheet_layout['result'] or 'cells' not in sheet_layout['result']['qLayout']:
        raise ValueError('query response structure is not as expected.')
    odf = pd.json_normalize(sheet_layout['result']['qLayout']['cells'])
    logger.debug('_get_sheet_objects_pandas function completed, len(df): %s', len(odf))
    return odf


def _get_object_ms_pandas(ws, object_handle):
    """
    Returns a dataframe with all measures used in object and their properties

    Args:
        ws (websocket): websocket connection
        object_handle (int): Object handle   

    Returns:
        dataframe: dataframe with all measures used in object and their properties
    """

    logger.debug('_get_object_ms_pandas function started, object_handle = %s', object_handle)
    query_result = query(ws, {
      "jsonrpc": "2.0",
      "id": _next_rpc_id(),
      "method": "GetProperties",
      "handle": object_handle,
      "params": []
    })

    if 'result' not in query_result or 'qProp' not in query_result['result']:
        raise ValueError('Query response structure is not as expected ([result][qProp]).')
    else: 
        if 'boxplotDef' in query_result['result']['qProp']:
            if 'qHyperCubeDef' not in query_result['result']['qProp']['boxplotDef'] or \
                    'qMeasures' not in query_result['result']['qProp']['boxplotDef']['qHyperCubeDef']:
                raise ValueError('Query response structure is not as expected \
                                 ([result][qProp][boxplotDef][qHyperCubeDef][qMeasures]).')
            odf = pd.json_normalize(query_result['result']['qProp']['boxplotDef']['qHyperCubeDef']['qMeasures'])
        else:
            if 'qHyperCubeDef' not in query_result['result']['qProp'] or \
                    'qMeasures' not in query_result['result']['qProp']['qHyperCubeDef']:
                raise ValueError('Query response structure is not as expected ([result][qProp][qHyperCubeDef][qMeasures]).')
            else: odf = pd.json_normalize(query_result['result']['qProp']['qHyperCubeDef']['qMeasures'])
    logger.debug('_get_object_ms_pandas function completed, len(df): %s', len(odf))
    return odf


def _get_object_dim_pandas(ws, object_handle: int) -> pd.DataFrame:
    """
    Returns a dataframe with all dimensions used in object and their properties

    Args:
        ws (websocket): websocket connection
        object_handle (int): Object handle  

    Returns:
        dataframe: dataframe with all dimensions used in object and their properties
    """

    logger.debug('_get_object_dim_pandas function started, object_handle = %s', object_handle)
    query_result = query(ws, {
      "jsonrpc": "2.0",
      "id": _next_rpc_id(),
      "method": "GetProperties",
      "handle": object_handle,
      "params": []
    })

    if 'result' not in query_result or 'qProp' not in query_result['result']:
        raise ValueError('Query response structure is not as expected ([result][qProp]).')
    else: 
        if 'boxplotDef' in query_result['result']['qProp']:
            if 'qHyperCubeDef' not in query_result['result']['qProp']['boxplotDef'] or \
                    'qDimensions' not in query_result['result']['qProp']['boxplotDef']['qHyperCubeDef']:
                raise ValueError('Query response structure is not as expected \
                                 ([result][qProp][boxplotDef][qHyperCubeDef][qDimensions]).')
            odf = pd.json_normalize(query_result['result']['qProp']['boxplotDef']['qHyperCubeDef']['qDimensions'])
        elif 'qInfo' in query_result['result']['qProp'] and 'qType' in query_result['result']['qProp']['qInfo'] and \
              query_result['result']['qProp']['qInfo']['qType']  == 'listbox':
            odf = pd.json_normalize(query_result['result']['qProp']['qListObjectDef'])
        else:
            if 'qHyperCubeDef' not in query_result['result']['qProp'] or \
                    'qDimensions' not in query_result['result']['qProp']['qHyperCubeDef']:
                raise ValueError('Query response structure is not as expected ([result][qProp][qHyperCubeDef][qDimensions]).')
            else: odf = pd.json_normalize(query_result['result']['qProp']['qHyperCubeDef']['qDimensions'])
    logger.debug('_get_object_dim_pandas function completed, len(df): %s', len(odf))
    return odf


def _get_object_subitem_pandas(ws, object_handle: int) -> pd.DataFrame:
    """
    Returns a dataframe with all subitems used in object and their properties

    Args:
        ws (websocket): websocket connection
        object_handle (int): Object handle

    Returns:
        dataframe: dataframe with all subitems used in object and their properties
    """

    logger.debug('_get_object_subitem_pandas function started, object_handle = %s', object_handle)
    query_result = query(ws, {
      "jsonrpc": "2.0",
      "id": _next_rpc_id(),
      "method": "GetChildInfos",
      "handle": object_handle,
      "params": []
    })

    if 'result' not in query_result or 'qInfos' not in query_result['result']:
        raise ValueError('Query response structure is not as expected ([result][qInfos]).')
    else: odf = pd.json_normalize(query_result['result']['qInfos'])
    logger.debug('_get_object_subitem_pandas function completed, len(df): %s', len(odf))
    return odf


def _get_hypercube_data(ws, handle: int, path: str = '/qHyperCubeDef') -> pd.DataFrame:
    """
    Fetches all data from an object's hypercube via GetHyperCubeData
    and returns it as a pandas DataFrame.

    Uses pagination to handle datasets larger than the Engine API limit
    of 10 000 cells per request.

    Args:
        ws: websocket connection
        handle (int): object handle
        path (str): hypercube definition path, default '/qHyperCubeDef'

    Returns:
        pd.DataFrame with dimension and measure columns

    Raises:
        ValueError: if layout structure is unexpected or hypercube is missing
    """
    logger.debug('_get_hypercube_data started, handle=%s, path=%s', handle, path)

    layout = _get_layout(ws, handle)
    if layout is None or 'result' not in layout or 'qLayout' not in layout['result']:
        raise ValueError('_get_hypercube_data: GetLayout returned unexpected structure.')

    q_layout = layout['result']['qLayout']
    if 'qHyperCube' not in q_layout:
        raise ValueError('_get_hypercube_data: object does not contain a hypercube.')

    hc = q_layout['qHyperCube']
    total_cols = hc['qSize']['qcx']
    total_rows = hc['qSize']['qcy']

    dim_info = hc.get('qDimensionInfo', [])
    ms_info = hc.get('qMeasureInfo', [])
    num_dims = len(dim_info)

    col_names = [d.get('qFallbackTitle', f'dim_{i}') for i, d in enumerate(dim_info)] + \
                [m.get('qFallbackTitle', f'ms_{i}') for i, m in enumerate(ms_info)]

    if total_rows == 0:
        logger.debug('_get_hypercube_data: empty dataset, returning empty DataFrame')
        return pd.DataFrame(columns=col_names)

    page_height = max(1, 10000 // total_cols)
    all_rows = []
    offset = 0

    while offset < total_rows:
        chunk = min(page_height, total_rows - offset)
        page_result = query(ws, {
            "jsonrpc": "2.0",
            "id": _next_rpc_id(),
            "method": "GetHyperCubeData",
            "handle": handle,
            "params": [path, [{"qTop": offset, "qLeft": 0,
                               "qWidth": total_cols, "qHeight": chunk}]]
        })

        if page_result is None or 'result' not in page_result:
            raise ValueError(f'_get_hypercube_data: GetHyperCubeData failed at offset {offset}.')

        data_pages = page_result['result'].get('qDataPages', [])
        if not data_pages:
            break

        for row in data_pages[0].get('qMatrix', []):
            parsed_row = []
            for i, cell in enumerate(row):
                if i < num_dims:
                    parsed_row.append(cell.get('qText', ''))
                else:
                    q_num = cell.get('qNum')
                    if q_num is not None and q_num == q_num:
                        parsed_row.append(q_num)
                    else:
                        parsed_row.append(cell.get('qText', ''))
            all_rows.append(parsed_row)

        offset += page_height

    df = pd.DataFrame(all_rows, columns=col_names)
    logger.info('_get_hypercube_data completed, shape=%s', df.shape)
    return df
