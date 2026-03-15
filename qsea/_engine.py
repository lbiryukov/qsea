import itertools
import json
import ssl
import time as _time
from typing import Optional, Union

import websocket

from qsea._config import config, logger

_rpc_counter = itertools.count(1)


def _next_rpc_id() -> int:
    """Return a unique JSON-RPC request id."""
    return next(_rpc_counter)


def query(ws, json_query: dict, attempts: int = 1) -> Union[dict, None]:
    """
    A shortcut to query Qlik Sense Engine Api

    Args:
        ws (websocket): websocket connection
        json_query (dict): query text
        attempts (int, optional): maximum number of attempts. Defaults to 1.

    Returns:
        Union[dict, None]: query result
        None if query failed
    """

    logger.debug('Query function started, query: %s', str(json_query))
    ws.send(json.dumps(json_query))
    i = 1
    skipped = 0
    max_skipped = 50

    error_text = ''
    while i <= attempts:
        try: 
            result = ws.recv()
            res = json.loads(result)
            if 'id' not in res:
                skipped += 1
                logger.debug('Skipping push notification (%d/%d): %s', skipped, max_skipped, str(res)[:config.logQueryMaxLength])
                if skipped >= max_skipped:
                    logger.error('Too many push notifications skipped (%d), aborting query', skipped)
                    return None
                continue
            if isinstance(res.get('result'), dict) and 'qReturn' not in res['result'] and 'qValue' in res['result']:
                res['result']['qReturn'] = res['result']['qValue']
            logger.debug('Query function completed, answer %s', str(res)[:config.logQueryMaxLength])
            return res
        except Exception as E:
            error_text = str(E)
            logger.exception('Unknown Error, attempt %s of %s; %s', i, attempts, error_text)
        i += 1
    logger.error('Query function completed with error, %s', error_text)
    return None


def _open_connection(qlik_url: str, header_user: dict, timeout: int = 10,
                     max_retries: int = 6, retry_delay: float = 10.0,
                     verify_ssl: bool = False):
    logger.debug('_open_connection function started, url = %s', qlik_url)

    if verify_ssl:
        ssl_opts = {}
    else:
        ssl_opts = {"cert_reqs": ssl.CERT_NONE}

    for attempt in range(1, max_retries + 1):
        ws = websocket.create_connection(qlik_url, sslopt=ssl_opts, header=header_user, timeout=timeout)
        result1 = ws.recv()
        parsed1 = json.loads(result1)
        if 'severity' in parsed1.get('params', {}):
            if parsed1['params']['severity'] == 'fatal':
                fatal_msg = parsed1['params']['message']
                logger.error('Failed to open connection (attempt %s/%s): %s', attempt, max_retries, fatal_msg)
                try:
                    ws.close()
                except Exception:
                    pass
                if 'MaxParallelSessionsExceeded' in fatal_msg and attempt < max_retries:
                    backoff = retry_delay * min(attempt, 4)
                    logger.info('Retrying in %.1f seconds (attempt %s/%s)...', backoff, attempt, max_retries)
                    _time.sleep(backoff)
                    continue
                raise ConnectionError(f'Qlik Engine connection failed: {fatal_msg}')
            else:
                logger.warning('Non-fatal notification (attempt %s/%s): %s',
                               attempt, max_retries, parsed1.get('params'))
                continue
        else:
            result2 = ws.recv()
            parsed2 = json.loads(result2)
            if parsed2.get('params', {}).get('qSessionState') in ['SESSION_ATTACHED', 'SESSION_CREATED']:
                logger.info('Connection opened, %s', parsed2['params']['qSessionState'])
                return ws
            logger.warning('Unexpected session state, returning connection: %s', parsed2)
            return ws
    raise ConnectionError(f'Qlik Engine connection failed after {max_retries} retries')


def _get_app_id(ws, app_name: str) -> Optional[str]:
    """
    Returns App GUID by its name

    Args:
        ws (websocket): websocket connection
        app_name (str): App name

    Returns:
        str: App GUID
        None if App not found
    """
    logger.debug('_get_app_id function started, app_name = %s', app_name)
    rawAppList = query(ws, {
        "handle": -1,
        "method": "GetDocList",
        "params": [],
        "outKey": -1,
        "id": _next_rpc_id()
        })
    
    if rawAppList is None or 'result' not in rawAppList or 'qDocList' not in rawAppList['result']:
        logger.error('_get_app_id function error. GetDocList returned unexpected response: %s', rawAppList)
        return None

    for app in rawAppList['result']['qDocList']:
        if app['qDocName'] == app_name:
            logger.debug('_get_app_id function completed, %s' , app['qDocId'])
            return app['qDocId']
        
    logger.error('_get_app_id function error. App not found, %s', app_name)
    return None


def _open_doc(ws, app_name: str = '', app_id: str = '') -> int:
    """
    Opens the app (by name or ID) and returns its handle

    Args:
        ws (websocket): websocket connection
        app_name (str, optional): App name. Defaults to ''.
        app_id (str, optional): App GUID. Defaults to ''.

    Returns:
        int: App handle
        0 if App not found, or could not be opened
    """

    logger.debug('_open_doc function started, app_name = %s, app_id = %s', app_name, app_id)
    if app_name == '' and app_id == '':
        logger.error('_open_doc function error. app_name or app_id not specified')
        return 0
    
    if app_id == '' and app_name != '':
        app_id = _get_app_id(ws, app_name)

    query_result = query(ws, {
    "handle": -1,
    "method": "OpenDoc",
    "params": [app_id],
    "outKey": -1,
    "id": _next_rpc_id()
    })

    if query_result is None:
        logger.error('_open_doc function error. OpenDoc returned no response. app_name = %s', app_name)
        return 0

    if 'result' in query_result and 'qReturn' in query_result['result'] and \
        'qHandle' in query_result['result']['qReturn']:
        res = query_result['result']['qReturn']['qHandle']
        logger.debug('_open_doc function completed, %s', res)
        return res
    elif 'error' in query_result and 'code' in query_result['error']:
        error_code = query_result['error']['code']
        error_msg = query_result['error'].get('message', '')
        if error_code == 1002:
            logger.info('App already open, app_id = %s, retrieving handle via GetActiveDoc', app_id)
            active_result = query(ws, {"handle": -1, "method": "GetActiveDoc", "params": [], "outKey": -1, "id": _next_rpc_id()})
            if active_result and 'result' in active_result and 'qReturn' in active_result['result'] \
                    and 'qHandle' in active_result['result']['qReturn']:
                res = active_result['result']['qReturn']['qHandle']
                logger.debug('_open_doc retrieved handle via GetActiveDoc, handle = %s', res)
                return res
            logger.warning('_open_doc: GetActiveDoc fallback failed for app_id = %s', app_id)
        else:
            logger.warning('_open_doc error: code=%s, message=%s, app_name=%s', error_code, error_msg, app_name)
        return 0
    else:
        logger.warning('_open_doc function error. OpenDoc method returned incorrect response. app_name = %s, response = %s', app_name, query_result)
        return 0


def _get_properties(ws, handle: int) -> dict:
    """
    A shortcut to get object properties by its handle

    Args:
        ws (websocket): websocket connection
        handle (int): object handle

    Returns:
        dict: object properties
    """
    logger.debug('_get_properties function started, handle = %s', handle)
    return query(ws, {
      "jsonrpc": "2.0",
      "id": _next_rpc_id(),
      "method": "GetProperties",
      "handle": handle,
      "params": []
    })


def _set_properties(ws, handle: int, params: dict) -> dict:
    """
    A shortcut to set object properties by its handle and set query

    Args:
        ws (websocket): websocket connection
        handle (int): object handle 
        params (dict): properties to set

    Returns:
        dict: result of the set query
    """
    logger.debug('_set_properties function started, handle = %s', handle)
    result = query(ws, {
              "jsonrpc": "2.0",
              "id": _next_rpc_id(),
              "method": "SetProperties",
              "handle": handle,
              "params": [
                params
                ]
            })
    return result


def _get_layout(ws, handle: int) -> dict:
    """
    A shortcut to get object layout by its handle

    Args:
        ws (websocket): websocket connection
        handle (int): object handle

    Returns:
        dict: object layout
    """
    logger.debug('_get_layout function started, handle = %s', handle)
    return query(ws, {
      "jsonrpc": "2.0",
      "id": _next_rpc_id(),
      "method": "GetLayout",
      "handle": handle,
      "params": []
    })


def _get_object_handle(ws, app_handle: int, object_id: str) -> int:
    """
    Returns a handle of any object by its ID

    Args:
        ws (websocket): websocket connection
        app_handle (int): App handle 
        object_id (str): Object ID

    Returns:
        int: Object handle
    """
    logger.debug('_get_object_handle function started, app_handle = %s, object_id = %s', app_handle, object_id)
    result = query(ws, {
      "jsonrpc": "2.0",
      "id": _next_rpc_id(),
      "method": "GetObject",
      "handle": app_handle,
      "params": [
        object_id
      ]
    })
    if result is None or 'result' not in result:
        logger.error('_get_object_handle failed for object_id = %s', object_id)
        return None
    return result['result']['qReturn']['qHandle']
