import uuid

from qsea._config import logger
from qsea._engine import query, _get_layout, _next_rpc_id


def _evaluate_expression(ws, app_handle: int, expression: str) -> dict:
    """
    Evaluates a Qlik expression via EvaluateEx Engine API method.

    Args:
        ws: websocket connection
        app_handle (int): handle of the open app
        expression (str): Qlik expression to evaluate

    Returns:
        dict: {"value": float or None, "text": str, "is_numeric": bool}
    """
    logger.debug('_evaluate_expression started, expression = %s', expression)

    expr = expression if expression.startswith('=') else '=' + expression
    result = query(ws, {
        "jsonrpc": "2.0",
        "id": _next_rpc_id(),
        "method": "EvaluateEx",
        "handle": app_handle,
        "params": {"qExpression": expr}
    })

    if result is None:
        raise ValueError('EvaluateEx returned no response.')
    if 'error' in result:
        raise ValueError(f"EvaluateEx error: {result['error']}")

    q_return = result.get('result', {}).get('qReturn', {})
    if isinstance(q_return, dict):
        return {
            "value": q_return.get('qNumber'),
            "text": q_return.get('qText', ''),
            "is_numeric": q_return.get('qIsNumeric', False)
        }
    return {"value": None, "text": str(q_return), "is_numeric": False}


def _clear_all(ws, app_handle: int) -> bool:
    """
    Clears all selections in the app via ClearAll Engine API method.

    Args:
        ws: websocket connection
        app_handle (int): handle of the open app

    Returns:
        bool: True if successful
    """
    logger.debug('_clear_all started, app_handle = %s', app_handle)
    result = query(ws, {
        "jsonrpc": "2.0",
        "id": _next_rpc_id(),
        "method": "ClearAll",
        "handle": app_handle,
        "params": [False]
    })
    if result is None:
        logger.error('_clear_all failed, no response')
        return False
    if 'error' in result:
        logger.error('_clear_all error: %s', result['error'])
        return False
    logger.debug('_clear_all completed')
    return True


def _get_field_handle(ws, app_handle: int, field_name: str) -> int:
    """
    Gets a field handle via GetField Engine API method.

    Args:
        ws: websocket connection
        app_handle (int): handle of the open app
        field_name (str): name of the field

    Returns:
        int: field handle

    Raises:
        ValueError: if the field is not found
    """
    logger.debug('_get_field_handle started, field_name = %s', field_name)
    result = query(ws, {
        "jsonrpc": "2.0",
        "id": _next_rpc_id(),
        "method": "GetField",
        "handle": app_handle,
        "params": [field_name]
    })
    if result is None:
        raise ValueError(f"Field '{field_name}' not found: no response from engine.")
    if 'error' in result:
        raise ValueError(f"Field '{field_name}' not found in the app data model.")

    handle = result.get('result', {}).get('qReturn', {}).get('qHandle')
    if handle is None:
        raise ValueError(f"Field '{field_name}': unexpected response format.")
    logger.debug('_get_field_handle completed, handle = %s', handle)
    return handle


def _select_field_values(ws, field_handle: int, values: list, toggle: bool = False) -> bool:
    """
    Selects values in a field via SelectValues Engine API method.

    Args:
        ws: websocket connection
        field_handle (int): handle of the field (from _get_field_handle)
        values (list): values to select
        toggle (bool): if True, toggle selection mode

    Returns:
        bool: True if successful
    """
    logger.debug('_select_field_values started, field_handle = %s, values = %s', field_handle, values)

    qfield_values = []
    for v in values:
        if isinstance(v, (int, float)):
            qfield_values.append({"qText": str(v), "qIsNumeric": True, "qNumber": float(v)})
        else:
            qfield_values.append({"qText": str(v), "qIsNumeric": False, "qNumber": 0})

    result = query(ws, {
        "jsonrpc": "2.0",
        "id": _next_rpc_id(),
        "method": "SelectValues",
        "handle": field_handle,
        "params": [qfield_values, toggle, False]
    })
    if result is None:
        logger.warning('_select_field_values: no response')
        return False
    if 'error' in result:
        logger.warning('_select_field_values error: %s', result['error'])
        return False
    logger.debug('_select_field_values completed')
    return True


def _create_session_hypercube(ws, app_handle: int, expression: str = None,
                              library_id: str = None,
                              context_set_expression: str = None) -> dict:
    """
    Creates a temporary session hypercube with one measure, evaluates it,
    and returns the result.

    Args:
        ws: websocket connection
        app_handle (int): handle of the open app
        expression (str): raw Qlik expression (mutually exclusive with library_id)
        library_id (str): ID of a master measure (mutually exclusive with expression)
        context_set_expression (str): Set Analysis applied to the whole cube

    Returns:
        dict: {"handle": int, "id": str, "value": float|None, "text": str, "is_numeric": bool}
    """
    logger.debug('_create_session_hypercube started, expression=%s, library_id=%s, context_set=%s',
                 expression, library_id, context_set_expression)

    object_id = 'eval_' + str(uuid.uuid4())[:8]

    measure_def = {}
    if library_id:
        measure_def = {"qLibraryId": library_id}
    elif expression:
        expr = expression if expression.startswith('=') else '=' + expression
        measure_def = {"qDef": {"qDef": expr}}
    else:
        raise ValueError('Either expression or library_id must be provided.')

    hc_def = {
        "qDimensions": [],
        "qMeasures": [measure_def],
        "qInitialDataFetch": [{"qTop": 0, "qLeft": 0, "qHeight": 1, "qWidth": 1}]
    }
    if context_set_expression:
        hc_def["qContextSetExpression"] = context_set_expression

    result = query(ws, {
        "jsonrpc": "2.0",
        "id": _next_rpc_id(),
        "method": "CreateSessionObject",
        "handle": app_handle,
        "params": [{
            "qInfo": {"qId": object_id, "qType": "eval-hc"},
            "qHyperCubeDef": hc_def
        }]
    })

    if result is None:
        raise ValueError('CreateSessionObject returned no response.')
    if 'error' in result:
        raise ValueError(f"CreateSessionObject error: {result['error']}")

    obj_handle = result['result']['qReturn']['qHandle']

    layout = _get_layout(ws, obj_handle)
    if layout is None:
        raise ValueError('GetLayout returned no response for session hypercube.')

    try:
        cell = layout['result']['qLayout']['qHyperCube']['qDataPages'][0]['qMatrix'][0][0]
        value = cell.get('qNum')
        text = cell.get('qText', '')
        is_numeric = cell.get('qIsNumeric', value is not None and text != '-')
    except (KeyError, IndexError) as e:
        raise ValueError(f'Unexpected hypercube layout structure: {e}')

    logger.debug('_create_session_hypercube completed, value=%s, text=%s', value, text)
    return {
        "handle": obj_handle,
        "id": object_id,
        "value": value,
        "text": text,
        "is_numeric": is_numeric
    }


def _get_field_values(ws, app_handle: int, field_name: str) -> set:
    """
    Returns the set of distinct values in a field by creating a temporary
    session ListObject, reading all data pages, then destroying the object.

    Values are returned as strings for uniform comparison.

    Args:
        ws: websocket connection
        app_handle (int): handle of the open app
        field_name (str): name of the field

    Returns:
        set: distinct field values as strings

    Raises:
        ValueError: if the field does not exist or the engine returns an error
    """
    logger.debug('_get_field_values started, field_name = %s', field_name)

    object_id = 'fval_' + str(uuid.uuid4())[:8]

    result = query(ws, {
        "jsonrpc": "2.0",
        "id": _next_rpc_id(),
        "method": "CreateSessionObject",
        "handle": app_handle,
        "params": [{
            "qInfo": {"qId": object_id, "qType": "field-values"},
            "qListObjectDef": {
                "qDef": {
                    "qFieldDefs": [field_name],
                    "qSortCriterias": [{"qSortByLoadOrder": 1}]
                },
                "qInitialDataFetch": [{"qTop": 0, "qLeft": 0, "qHeight": 10000, "qWidth": 1}]
            }
        }]
    })

    if result is None:
        raise ValueError(f"Failed to create ListObject for field '{field_name}': no response.")
    if 'error' in result:
        raise ValueError(f"Field '{field_name}' not found in the app data model.")

    obj_handle = result['result']['qReturn']['qHandle']

    try:
        layout = _get_layout(ws, obj_handle)
        if layout is None:
            raise ValueError(f"GetLayout returned no response for field '{field_name}'.")

        data_pages = layout['result']['qLayout']['qListObject']['qDataPages']
        values = set()
        for page in data_pages:
            for row in page.get('qMatrix', []):
                for cell in row:
                    text = cell.get('qText')
                    if text is not None and cell.get('qState') != 'X':
                        values.add(text)
        logger.debug('_get_field_values completed, field=%s, count=%d', field_name, len(values))
        return values
    finally:
        _destroy_session_object(ws, app_handle, object_id)


def _validate_filter_values(ws, app_handle: int, filters: dict) -> dict:
    """
    Validates that filter values exist in their respective fields.

    For each field in filters, queries the engine for the field's distinct values
    and checks whether the requested filter values are present.

    Args:
        ws: websocket connection
        app_handle (int): handle of the open app
        filters (dict): field -> value(s) mapping

    Returns:
        dict: {field_name: [missing_values]} for fields with missing values.
              Empty dict means all values are valid.

    Raises:
        ValueError: if a field does not exist in the data model
    """
    logger.debug('_validate_filter_values started, filters = %s', filters)
    missing = {}

    for field_name, values in filters.items():
        if not isinstance(values, list):
            values = [values]

        actual_values = _get_field_values(ws, app_handle, field_name)
        actual_str = actual_values

        not_found = []
        for v in values:
            if str(v) not in actual_str:
                not_found.append(v)

        if not_found:
            missing[field_name] = not_found

    logger.debug('_validate_filter_values completed, missing = %s', missing)
    return missing


def _destroy_session_object(ws, app_handle: int, object_id: str) -> bool:
    """
    Destroys a session object via DestroySessionObject Engine API method.

    Args:
        ws: websocket connection
        app_handle (int): handle of the open app
        object_id (str): qId of the session object to destroy

    Returns:
        bool: True if successful
    """
    logger.debug('_destroy_session_object started, object_id = %s', object_id)
    result = query(ws, {
        "jsonrpc": "2.0",
        "id": _next_rpc_id(),
        "method": "DestroySessionObject",
        "handle": app_handle,
        "params": [object_id]
    })
    if result is None:
        logger.warning('_destroy_session_object: no response')
        return False
    if 'error' in result:
        logger.warning('_destroy_session_object error: %s', result['error'])
        return False
    logger.debug('_destroy_session_object completed')
    return True
