#!/usr/bin/env python
# coding: utf-8

# In[1]:


# beta for publish

import json
import pandas as pd
import datetime as dt
import logging
import websocket
import ssl
import uuid
from typing import List, Dict, Tuple, Optional, Union

# In[2]:


def setup_logging(log_file_path, log_level=logging.info, log_format=None):
    if log_format is None:
        log_format = '%(asctime)s \t LineNo: %(lineno)s \t %(funcName)20s() \t %(levelname)s: %(message)s'

    logging.basicConfig(
        level=log_level,
        filename=log_file_path,
        filemode="w",
        format=log_format
    )

class Config:
    def __init__(self) -> None:
        self.logQueryMaxLength = 300

logger = logging.getLogger(__name__)
config = Config()

def _test():
    # for testing purposes
    const = 38
    logger.info('Test function completed, %s', const)
    return const


def _to_qlik(string):
    # add quotes to string - is used to put strings into json queries
    if string is None: return ""
    else: return '"' + str(string) + '"'

def _find_key(key, dictionary):
    # is used to check if there is instance in the json result of Query function
    if key in dictionary:
        return True
    for k, v in dictionary.items():
        if isinstance(v, dict):
            if _find_key(key, v):
                return True
    return False

def _open_connection(qlik_url: str, header_user: dict, timeout: int = 10):
    #to refine: review the overall config
    logger.debug('_open_connection function started')
    ws = websocket.create_connection(qlik_url, sslopt={"cert_reqs": ssl.CERT_NONE},header=header_user, timeout = timeout)
    result1 = ws.recv()
    if 'severity' in json.loads(result1)['params']:
        if json.loads(result1)['params']['severity'] == 'fatal':
            logger.error('Failed to open connection, %s', json.loads(result1)['params']['message'])
            return ws
    else: 
        result2 = ws.recv()
        if json.loads(result2)['params']['qSessionState'] in ['SESSION_ATTACHED', 'SESSION_CREATED']:
            logger.info ('Connection opened, %s', json.loads(result2)['params']['qSessionState'])
            return ws
    logger.debug('_open_connection function completed')
    return ws

class Connection:
    """
    The class that represents a dictionary of websocket connections to Qlik Sense Engine Api
    Since one websocket connection can be used only for one app, this class is used to handle all websocket connections
    New websocket connections are created automatically when a new app object is created
    """
    
    def __init__(self, header_user, qlik_url, timeout: int = 10):
        logger.debug('Connection class started')
        self.header_user = header_user
        self.qlik_url = qlik_url
        self.timeout = timeout
        
        # main connection is used for the first app
        self.main_ws = _open_connection(qlik_url, header_user, timeout)
        
        # by default the main_app_id is empty; when the first app is opened, it is assigned to main_app
        self.main_app_id = None
        self.df = _get_app_list(self.main_ws)

        # wss is a dictionary of secondary connections
        self.wss = {}

    def reload_app_list(self):
        """
        Reloads the list of apps, in case if new apps were added after the Connection object was created
        """
        self.df = _get_app_list(self.main_ws)


# In[3]:

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

    ErrorText = ''
    while i <= attempts:
        try: 
            result = ws.recv()
            res = json.loads(result)
            logger.debug('Query function completed, answer %s', str(res)[:config.logQueryMaxLength])
            return res
        except Exception as E:
            ErrorText = str(E)
            logger.exception('Unknown Error, attempt %s of %s; %s', i, attempts, ErrorText)
        i += 1
    logger.error('Query function completed with error, %s', ErrorText)
    return None

# query({
#         "handle": -1,
#         "method": "GetActiveDoc",
#         "params": [],
#         "outKey": -1,
#         "id": 1
#         })


# In[4]:

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
        "id": 1
        })
    
    for app in rawAppList['result']['qDocList']:
        if app['qDocName'] == app_name:
            logger.debug('_get_app_id function completed, %s' , app['qDocId'])
            return app['qDocId']
        
    logger.error('_get_app_id function error. App not found, %s', app_name)
    return None
    
# _get_app_id('Myapp_name')


# In[5]:


def _open_doc(ws, app_name: str = '', AppID: str = '') -> int:
    """
    Opens the app (by name or ID) and returns its handle

    Args:
        ws (websocket): websocket connection
        app_name (str, optional): App name. Defaults to ''.
        AppID (str, optional): App GUID. Defaults to ''.

    Returns:
        int: App handle
        0 if App not found, or could not be opened
    """

    logger.debug('_open_doc function started, app_name = %s, AppID = %s', app_name, AppID)
    if app_name == '' and AppID == '':
        logger.error('_open_doc function error. app_name or AppID not specified')
        return 0
    
    if app_name != '':
        AppID = _get_app_id(ws, app_name)

    query_result = query(ws, {
    "handle": -1,
    "method": "OpenDoc",
    "params": [AppID],
    "outKey": -1,
    "id": 1
    })

    if 'result' in query_result and 'qReturn' in query_result['result'] and \
        'qHandle' in query_result['result']['qReturn']:
        res = query_result['result']['qReturn']['qHandle']
        logger.debug('_open_doc function completed, %s', res)
        return res
    else:
        logger.error('_open_doc function error. OpenDoc method returned incorrect response. app_name = %s, response = %s', app_name, query_result)
        return 0
    
# app_handle = _open_doc('Myapp_name')


# In[6]:

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
      "id": 4,
      "method": "GetProperties",
      "handle": handle,
      "params": []
    })


# In[7]:

def _set_properties(ws, handle: int, query: dict) -> dict:
    """
    A shortcut to set object properties by its handle and set query

    Args:
        ws (websocket): websocket connection
        handle (int): object handle 
        query (dict): set query

    Returns:
        dict: result fo the set query
    """
    logger.debug('_set_properties function started, handle = %s', handle)
    zu = query(ws, {
              "jsonrpc": "2.0",
              "id": 4,
              "method": "SetProperties",
              "handle": handle,
              "params": [
                query
                ]
            })
    return zu


# In[8]:

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
      "id": 4,
      "method": "GetLayout",
      "handle": handle,
      "params": []
    })


# In[9]:

def _get_object_handle(ws, app_handle: int, ObjectId: str) -> int:
    """
    Returns a handle of any object by its ID

    Args:
        ws (websocket): websocket connection
        app_handle (int): App handle 
        ObjectId (str): Object ID

    Returns:
        int: Object handle
    """
    logger.debug('_get_object_handle function started, app_handle = %s, ObjectId = %s', app_handle, ObjectId)
    return query(ws, {
      "jsonrpc": "2.0",
      "id": 4,
      "method": "GetObject",
      "handle": app_handle,
      "params": [
        ObjectId
      ]
    })['result']['qReturn']['qHandle']


# In[10]:

def _get_app_list(ws) -> pd.DataFrame:
    """
    Returns a dataframe with all apps and their properties

    Args:
        ws (websocket): websocket connection

    Returns:
        dataframe: dataframe with all apps and their properties
    """
    logger.debug('_get_app_list function started')

    zu = query(ws, {
        "handle": -1,
        "method": "GetDocList",
        "params": [],
        "outKey": -1,
        "id": 1
        })
    
    df = pd.json_normalize(zu['result']['qDocList'])
    logger.debug('_get_app_list function completed, len(df): %s', len(df))
    return df


# In[70]:

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
    # get handle of VariableList
    query_result = query(ws, {
          "jsonrpc": "2.0",
          "id": 2,
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
    list_handle = query_result['result']['qReturn']['qHandle']
    
    layout = _get_layout(ws, list_handle)
    if 'result' not in layout or 'qLayout' not in layout['result'] \
            or 'qVariableList' not in layout['result']['qLayout'] \
            or 'qItems' not in layout['result']['qLayout']['qVariableList']:
        raise ValueError('Layout structure is not as expected.')
    
    df = pd.json_normalize(layout['result']['qLayout']['qVariableList']['qItems'])
    logger.debug(f'_get_var_pandas function completed, len(df): {len(df)}')
    return df

# zu = GetVarList(1)


# In[71]:

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
    # get handle of MeasureList
    query_result = query(ws, {
          "jsonrpc": "2.0",
          "id": 2,
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

    list_handle = query_result['result']['qReturn']['qHandle']

    layout = _get_layout(ws, list_handle)
    if 'result' not in layout or 'qLayout' not in layout['result'] \
            or 'qMeasureList' not in layout['result']['qLayout'] \
            or 'qItems' not in layout['result']['qLayout']['qMeasureList']:
        raise ValueError('Layout structure is not as expected.')
    
    df = pd.json_normalize(layout['result']['qLayout']['qMeasureList']['qItems'])
    logger.debug(f'_get_ms_pandas function completed, len(df): {len(df)}')
    return df

# zu = GetMsList(1)


# In[72]:

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
    # get handle of SessionLists
    query_result = query(ws, {
      "jsonrpc": "2.0",
      "id": 2,
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
    
    list_handle = query_result['result']['qReturn']['qHandle']
    
    layout = _get_layout(ws, list_handle)
    if 'result' not in layout or 'qLayout' not in layout['result'] or 'qAppObjectList' not in layout['result']['qLayout'] or \
        'qItems' not in layout['result']['qLayout']['qAppObjectList']:
        raise ValueError('Layout structure is not as expected.')
    
    df = pd.json_normalize(layout['result']['qLayout']['qAppObjectList']['qItems'])
    logger.debug('_get_sheet_pandas function completed, len(df): %s', len(df))
    return df

# zu = GetSheetList(1)


# In[14]:

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

    # GetTablesAndKeys
    query_result = query(ws, {
      "jsonrpc": "2.0",
      "id": 1,
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

# zu = GetFieldList(1)


# In[73]:

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
    
    # get handle of DimensionList
    query_result = query(ws, {
          "jsonrpc": "2.0",
          "id": 2,
          "method": "CreateSessionObject",
          "handle": 1,
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

    if 'result' not in query_result or 'qReturn' not in query_result['result'] or 'qHandle' not in query_result['result']['qReturn']:
        raise ValueError('Query response structure is not as expected.')

    listHandle = query_result['result']['qReturn']['qHandle']
    df = pd.json_normalize(_get_layout(ws, listHandle)['result']['qLayout']['qDimensionList']['qItems'])
    df['qDimFieldDefs'] = 'Unknown'
    df['qDimFieldGrouping'] = 'Unknown'
    df['qDimFieldLabels'] = 'Unknown'


    # since the DimensionList method does not return the field name, we need to get it from each dimension separately
    for i in range(len(df)):

        dimhandle = query(ws, {
            "jsonrpc": "2.0",
            "id": 4,
            "method": "GetDimension",
            "handle": app_handle,
            "params": [df['qInfo.qId'][i]]
        })['result']['qReturn']['qHandle']


        query_result = query(ws, {
            "jsonrpc": "2.0",
            "id": 3,
            "method": "GetProperties",
            "handle": dimhandle,
            "params": {}
            })
        
        df.at[i, 'qDimFieldDefs'] = query_result["result"]["qProp"]['qDim']['qFieldDefs']
        df.at[i, 'qDimFieldGrouping'] = query_result["result"]["qProp"]['qDim']['qGrouping']
        df.at[i, 'qDimFieldLabels'] = query_result["result"]["qProp"]['qDim']['qFieldLabels']

    logger.debug('_get_dim_pandas function completed, len(df): %s', len(df))
    return df

# zu = _get_dim_pandas(1)


# In[16]:


# version 0.1.23-05-03
# returns dataframe with objects on the sheet by its handle

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

    # get objects on the sheet
    sheet_layout = _get_layout(ws, sheet_handle)
    if 'result' not in sheet_layout or 'qLayout' not in sheet_layout['result'] or 'cells' not in sheet_layout['result']['qLayout']:
        raise ValueError('query response structure is not as expected.')
    odf = pd.json_normalize(sheet_layout['result']['qLayout']['cells'])
    logger.debug('_get_sheet_objects_pandas function completed, len(df): %s', len(odf))
    return odf


# In[17]:

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
      "id": 4,
      "method": "GetProperties",
      "handle": object_handle,
      "params": []
    })

    if 'result' not in query_result or 'qProp' not in query_result['result']:
        raise ValueError('Query response structure is not as expected ([result][qProp]).')
    else: 
        if 'boxplotDef' in query_result['result']['qProp']:
        # there is special structure for boxplot
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

  


# In[18]:

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
      "id": 4,
      "method": "GetProperties",
      "handle": object_handle,
      "params": []
    })

    if 'result' not in query_result or 'qProp' not in query_result['result']:
        raise ValueError('Query response structure is not as expected ([result][qProp]).')
    else: 
        if 'boxplotDef' in query_result['result']['qProp']:
        # there is special structure for boxplot
            if 'qHyperCubeDef' not in query_result['result']['qProp']['boxplotDef'] or \
                    'qDimensions' not in query_result['result']['qProp']['boxplotDef']['qHyperCubeDef']:
                raise ValueError('Query response structure is not as expected \
                                 ([result][qProp][boxplotDef][qHyperCubeDef][qDimensions]).')
            odf = pd.json_normalize(query_result['result']['qProp']['boxplotDef']['qHyperCubeDef']['qDimensions'])
        else:
            if 'qHyperCubeDef' not in query_result['result']['qProp'] or \
                    'qDimensions' not in query_result['result']['qProp']['qHyperCubeDef']:
                raise ValueError('Query response structure is not as expected ([result][qProp][qHyperCubeDef][qDimensions]).')
            else: odf = pd.json_normalize(query_result['result']['qProp']['qHyperCubeDef']['qDimensions'])
    logger.debug('_get_object_dim_pandas function completed, len(df): %s', len(odf))
    return odf


# In[44]:

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

        # check if conn is already used; if not, add App as the main app
        if conn.main_app_id is None:
            self.ws = conn.main_ws
            conn.main_app_id = self.id
            logger.debug('App %s is set as the main app', self.name)
        
        # if current App is the main app, use existing main connection
        elif conn.main_app_id == self.id:
            self.ws = conn.main_ws
            logger.debug('App %s is already set as the main app', self.name)
        else:
            # if app_id is already in the list of secondary apps, use existing connection
            if self.id in conn.wss.keys():
                self.ws = conn.wss[self.id]
                logger.debug('App %s is already set as a secondary app', self.name)
            # else add app_id to the list of secondary apps and open new secondary connection
            else:
                conn.wss[self.id] = _open_connection(conn.qlik_url + self.id, conn.header_user, conn.timeout)
                self.ws = conn.wss[self.id]
                logger.debug('App %s is added as a secondary app', self.name)

        self.handle = _open_doc(self.ws, app_name)
        if self.handle == 0:
            logger.error('App %s is not opened', self.name)
            raise ValueError('App ' + self.name + ' is not opened.')
        self.variables = AppChildren(self, 'variables')
        self.measures = AppChildren(self, 'measures')
        self.sheets = AppChildren(self, 'sheets')
        self.fields = AppChildren(self, 'fields')
        self.dimensions = AppChildren(self, 'dimensions')
        
    def save(self):
        """
        Saves the application on the Qlik Sense Server
        """
        logger.debug('App.save function started, %s', self.name)
        query_result = query(self.ws, {
            "jsonrpc": "2.0",
            "id": 6,
            "method": "DoSave",
            "handle": self.handle,
            "params": []
        })

        if 'change' in query_result and query_result['change'][0] == 1:
            logger.info('App.save function completed, %s', self.name)
            return True
        
        logger.error('App.save function completed, DoSave method returned incorrect response, %s', self.name)
        return False

    def reload_data (self):
        """
        Reloads the data in the application on the Qlik Sense Server
        """
        logger.debug('App.reload_data function started, %s', self.name)
        
        js = {
                "jsonrpc": "2.0",
                "id": 2,
                "method": "DoReloadEx",
                "handle": self.handle,
                "params": []
            }
        query_result = query(self.ws, js)
        # to refine: check the response
        logger.debug('App.reload_data function completed, %s', self.name)
            

    def load(self, depth: int=1):
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

        if depth >= 2:
            for sh in self.sheets:
                sh.load()
                if depth >= 3:
                    for obj in sh.objects:
                        if obj.type in ['distributionplot', 'piechart', 'table', 'barchart',
       'pivot-table', 'boxplot', 'histogram', 'gauge', 'bulletchart',
       'mekkochart', 'treemap', 'waterfallchart', 'kpi', 'combochart',
       'scatterplot']:
                            obj.load()

        logger.debug('App.load function completed, %s', self.name)

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


# In[24]:

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


# In[65]:

class AppChildren():
    """
    The class, representing different collections of app objects, like master measures or dimensions
    A child of App class
    """
    def __init__(self, parent, _type):
        self.children = {}
        self.count = 0
        self.parent = parent
        self.ws = parent.ws
        self.app_handle = parent.handle
        self._type = _type
        
    def __getitem__(self, childName):
        logger.debug('AppChildren.__getitem__ function started, _type = %s, childName = %s', self._type, childName)
        return self.children[childName]
    
    def __setitem__(self, childName, var):
        logger.debug('AppChildren.__setitem__ function started, _type = %s, childName = %s', self._type, childName)
        self.children[childName] = var
            
    def __delitem__(cls, childName):
        logger.debug('AppChildren.__delitem__ function started, _type = %s, childName = %s', cls._type, childName)
        del cls.children[childName]
        cls.count -= 1
            
    def __iter__(self):
        # initializing collection if empty
        logger.debug('AppChildren.__iter__ function started')
        if self.count == 0:
            try: zvb = self['']
            except: logger.debug('AppChildren.__iter__ function, collection is empty, loading...')
        return ChildrenIterator(self)
    
    def load(self) -> bool:
        """
        Load the collection of objects from Qlik Sense app into the class instance
        """

        logger.debug('AppChildren.load function started, _type = %s', self._type)

        if self.count == 0:
            if self._type == 'variables':
                self.df = _get_var_pandas(self.parent.ws, self.app_handle)
                if len(self.df) == 0:
                    logger.debug('AppChildren.load function, no variables found')
                    return True
                for varName in self.df['qName']:
                    var = Variable(self, varName)
                    var.app_handle = self.app_handle
                    
                    row = self.df[self.df['qName'] == varName].iloc[0]
                    var.id = row['qInfo.qId']
                    if 'qDefinition' in self.df.columns: var.definition = row['qDefinition']
                    if 'qDescription' in self.df.columns: var.description = row['qDescription']
                    if 'qIsScriptCreated' in self.df.columns: var.script_created = row['qIsScriptCreated']
                    if str(var.script_created) == 'nan': var.script_created = False

                    self[varName] = var
                    self.count += 1
                    logger.debug('AppChildren.load function, variable object created, varName = %s, var.id = %s', varName, var.id)

            if self._type == 'measures':
                self.df = _get_ms_pandas(self.parent.ws, self.app_handle)
                if len(self.df) == 0:
                    logger.debug('AppChildren.load function, no measures found')
                    return True
                for msName in self.df['qMeta.title']:
                    ms = Measure(self, msName)
                    ms.app_handle = self.app_handle

                    row = self.df[self.df['qMeta.title'] == msName].iloc[0]
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
                    if 'qMeta.createdDate' in self.df.columns: 
                        try: ms.created_date = dt.datetime.strptime(row['qMeta.createdDate'], '%Y-%m-%dT%H:%M:%S.%fZ')
                        except: pass
                    if 'qMeta.modifiedDate' in self.df.columns: 
                        try: ms.modified_date = dt.datetime.strptime(row['qMeta.modifiedDate'], '%Y-%m-%dT%H:%M:%S.%fZ')
                        except: pass

                    self[msName] = ms
                    self.count += 1
                    logger.debug('AppChildren.load function, measure object created, msName = %s, ms.id = %s', msName, ms.id)
                        
            if self._type == 'sheets':
                self.df = _get_sheet_pandas(self.parent.ws, self.app_handle)
                if len(self.df) == 0:
                    logger.debug('AppChildren.load function, no sheets found')
                    return True
                for shName in self.df['qMeta.title']:
                    sh = Sheet(self, shName)
                    sh.app_handle = self.app_handle
                    
                    row = self.df[self.df['qMeta.title'] == shName].iloc[0]
                    sh.id = row['qInfo.qId']
                    if 'qMeta.description' in self.df.columns: sh.description = row['qMeta.description']
                    if 'qMeta.created_date' in self.df.columns: sh.created_date = dt.datetime.strptime(row['qMeta.createdDate'], '%Y-%m-%dT%H:%M:%S.%fZ')
                    if 'qMeta.modifiedDate' in self.df.columns: sh.modified_date = dt.datetime.strptime(row['qMeta.modifiedDate'], '%Y-%m-%dT%H:%M:%S.%fZ')
                    if 'qMeta.published' in self.df.columns: sh.published = row['qMeta.published']
                    if 'qMeta.approved' in self.df.columns: sh.approved = row['qMeta.approved']
                    if 'qMeta.owner.id' in self.df.columns: sh.ownerId = row['qMeta.owner.id']
                    if 'qMeta.owner.name' in self.df.columns: sh.ownerName = row['qMeta.owner.name']

                    self[shName] = sh
                    self.count += 1
                    logger.debug('AppChildren.load function, sheet object created, shName = %s, sh.id = %s', shName, sh.id)
                    
            if self._type == 'fields':
                self.df = _get_field_pandas(self.parent.ws, self.app_handle)
                if len(self.df) == 0:
                    logger.debug('AppChildren.load function, no fields found')
                    return True
                for fName in self.df['qFields.qName']:
                    f = Field(fName)
                    f.app_handle = self.app_handle
                    
                    row = self.df[self.df['qFields.qName'] == fName].iloc[0]
                    if 'qName' in self.df.columns: f.tableName = row['qName']
                    if 'qFields.qInformationDensity' in self.df.columns: f.informationDensity = row['qFields.qInformationDensity']
                    if 'qFields.qnNonNulls' in self.df.columns: f.nNonNulls = row['qFields.qnNonNulls']
                    if 'qFields.qnRows' in self.df.columns: f.nRows = row['qFields.qnRows']
                    if 'qFields.qSubsetRatio' in self.df.columns: f.subsetRatio = row['qFields.qSubsetRatio']
                    if 'qFields.qnTotalDistinctValues' in self.df.columns: f.nTotalDistinctValues = row['qFields.qnTotalDistinctValues']
                    if 'qFields.qnPresentDistinctValues' in self.df.columns: f.nPresentDistinctValues = row['qFields.qnPresentDistinctValues']
                    if 'qFields.qKeyType' in self.df.columns: f.keyType = row['qFields.qKeyType']
                    if 'qFields.qTags' in self.df.columns: f.tags = row['qFields.qTags']

                    self[fName] = f
                    self.count += 1
                    logger.debug('AppChildren.load function, field object created, fName = %s', fName)
                    
            if self._type == 'dimensions':
                self.df = _get_dim_pandas(self.parent.ws, self.app_handle)
                if len(self.df) == 0:
                    logger.debug('AppChildren.load function, no dimensions found')
                    return True
                for dimName in self.df['qMeta.title']:
                    dim = Dimension(self, dimName)
                    dim.app_handle = self.app_handle

                    row = self.df[self.df['qMeta.title'] == dimName].iloc[0]
                    dim.id = row['qInfo.qId']
                    dim.definition = row['qDimFieldDefs'] 
                    dim.label = row['qDimFieldLabels']
                    try: dim.created_date = dt.datetime.strptime(row['qMeta.createdDate'], '%Y-%m-%dT%H:%M:%S.%fZ')
                    except: pass
                    try: dim.modified_date = dt.datetime.strptime(row['qMeta.modifiedDate'], '%Y-%m-%dT%H:%M:%S.%fZ')
                    except: pass

                    self[dimName] = dim
                    self.count += 1
                    logger.debug('AppChildren.load function, dimension object created, dimName = %s, dim.id = %s', dimName, dim.id)
        
        else:
            logger.warning('AppChildren.load function, variables already loaded, recreate the App object to reload')
        logger.debug('AppChildren.load function finished, _type = %s', self._type)
        return True

    
    def add(self, name: str, definition: str, description: str = '', label: str = '', label_expression: str = '', format_type: str = 'U', \
                           format_ndec: int = 10, format_use_thou: int = 0, format_dec: str = ',', format_thou: str = '') -> bool:
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

        Returns:
            bool: True if the object was created successfully, False otherwise.
        """
        
        logger.debug('AppChildren.add function started, type = %s, name = %s, definition = %s, description = %s, label = %s', \
                     self._type, name, definition, description, label)
        if self._type == 'variables':
            query_result = query(self.parent.ws, {
                "jsonrpc": "2.0",
                "id": 4,
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
                return False
            
            var = Variable(self, name)
            var.app_handle = self.app_handle

            # renew variables data from app
            # to refine: don't renew the whole list, only refresh the exact variable
            self.df = _get_var_pandas(self.ws, self.app_handle)
            row = self.df[self.df['qName'] == name].iloc[0]
            var.id = row['qInfo.qId']
            if 'qDefinition' in self.df.columns: var.definition = row['qDefinition']
            if 'qDescription' in self.df.columns: var.description = row['qDescription']
            if 'qIsScriptCreated' in self.df.columns: var.script_created = row['qIsScriptCreated']
            if str(var.script_created) == 'nan': var.script_created = False

            self[name] = var
            self.count += 1
            logger.info('Variable created: %s, definition: %s, description: %s', name, definition, description)
            return True
        
        if self._type == 'measures':
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

                # renew measures data from app
                # to refine: query data for exact measure instead of the whole list
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
                try: ms.created_date = dt.datetime.strptime(row['qMeta.createdDate'], '%Y-%m-%dT%H:%M:%S.%fZ')
                except: pass
                try: ms.modified_date = dt.datetime.strptime(row['qMeta.modifiedDate'], '%Y-%m-%dT%H:%M:%S.%fZ')
                except: pass

                self[name] = ms
                self.count += 1
                logger.info('Measure created: %s, definition: %s, label: %s', name, definition, label)
                return True
            else: 
                logger.error('Failed to create measure: %s', name)
                return False
        
        if self._type == 'dimensions':
            # if definition or labels are strings, convert them to lists
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
                            "qFieldLabels": label
                                },
                        "qMetaDef": {"title": name, "description": description, "tags": []}
                        }]
                }
            # create new dimension
            query_result = query(self.parent.ws, t)
            
            if 'result' in query_result and 'qReturn' in query_result['result'] \
                    and 'qHandle' in query_result['result']['qReturn'] \
                    and query_result['result']['qReturn']['qHandle'] > 0:

                dim = Dimension(self, name)
                dim.app_handle = self.app_handle
                dim.handle = query_result['result']['qReturn']['qHandle']

                # download properties of the new dimension
                prop_result = query(self.parent.ws, {
                    "jsonrpc": "2.0",
                    "id": 3,
                    "method": "GetProperties",
                    "handle": dim.handle,
                    "params": {}
                    })

                # add new line to df
                dim.id = prop_result['result']['qProp']['qInfo']['qId']
                self.df = pd.concat([self.df, pd.DataFrame({col: [dim.id] if col == 'qInfo.qId' else None for col in self.df.columns})])
                self.df.reset_index(inplace=True)   # otherwise the list can not be added to the df
                row_label = self.df.index[self.df['qInfo.qId'] == dim.id].tolist()[0]
                self.df.at[row_label, 'qMeta.title'] = dim.name

                # renew dimensions data from app
                if _find_key('qFieldDefs', prop_result): 
                    dim.definition = prop_result['result']['qProp']['qDim']['qFieldDefs']
                    self.df.at[row_label, 'qDimFieldDefs'] = dim.definition
                if _find_key('qFieldLabels', prop_result): 
                    dim.label = prop_result['result']['qProp']['qDim']['qFieldLabels']
                    self.df.at[row_label, 'qDimFieldLabels'] = dim.label

                #self.df['qDimFieldDefs'] = self.df['qDimFieldDefs'].astype('object')

                self[name] = dim
                self.count += 1
                logger.info('Dimension created: %s, definition: %s, label: %s', name, definition, label)
                return True
            else: 
                logger.error('Failed to create dimension: %s', name)
                return False
            
        if self._type not in ['measures', 'dimensions', 'variables']:
            logger.error('Creation of %s is not supported', self._type)
            return False



# In[64]:

class Variable:
    """
    The class, representing the variables of the application
    Member of the App.variables collection
    """

    def __init__(self, parent, varName):
        self.name = varName
        self.handle = 0
        self.app_handle = 0
        self.parent = parent

        self.id = ''
        self.definition = ''
        self.description = ''
        self.created_date = dt.datetime(year=1901, month=1, day=1)
        self.modified_date = dt.datetime(year=1901, month=1, day=1)
        self.script_created = ''
        
        
    def get_handle(self) -> int:
        """
        Gets the handle of the variable
        """
        logger.debug('Variable.get_handle function started, %s', self.name)
        self.handle = query(self.parent.ws, {
          "jsonrpc": "2.0",
          "id": 4,
          "method": "GetVariableById",
          "handle": self.app_handle,
          "params": [self.id]
        })['result']['qReturn']['qHandle']
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
            if str(self.definition) == 'nan': definition = None
            else: definition = str(self.definition)
        if description is None:
            if str(self.description) == 'nan': description = None
            else: description = str(self.description)
        
        query_result = query(self.parent.parent.ws, {
          "jsonrpc": "2.0",
          "id": 2,
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
        zu = query(self.parent.ws, {
              "jsonrpc": "2.0",
              "id": 10,
              "method": "DestroyVariableById",
              "handle": self.app_handle,
              "params": [
                self.id
              ]
            })
        
        # delete value from variables collection
        logger.debug('Deleting variable from variables collection: %s', self.name)
        if zu['result']['qSuccess']:
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
        if str(tdesc) == 'nan': tdesc = ''

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


# In[21]:

class Field:
    """
    The class, representing the fields of the application
    Member of the App.fields collection
    """
    def __init__(self, fieldName):
        self.name = fieldName
        self.handle = 0
        self.app_handle = 0
        
        self.tableName = ''
        self.informationDensity, self.nNonNulls, self.nRows, self.subsetRatio = 0, 0, 0, 0
        self.nTotalDistinctValues, self.nPresentDistinctValues = 0, 0
        self.keyType, self.tags = '', ''


# In[22]:

class Measure:
    """
    The class, representing the master measures of the application
    Member of the App.measures collection
    """
    def __init__(self, parent, msName):
        self.name = msName
        self.handle = 0
        self.app_handle = 0
        self.parent = parent
        
        self.id, self.definition, self.description, self.label, self.label_expression = '', '', '', '', ''
        self.format_type, self.format_ndec, self.format_use_thou, self.format_dec, self.format_thou = '', -1, -1, '', ''
        self.created_date, self.modified_date = dt.datetime(year=1901, month=1, day=1), dt.datetime(year=1901, month=1, day=1)
        
    def get_handle(self) -> int:
        """
        Gets the handle of the measure
        """
        logger.debug('Measure.get_handle function started, %s', self.name)
        self.handle = query(self.parent.ws, {
          "jsonrpc": "2.0",
          "id": 4,
          "method": "GetMeasure",
          "handle": self.app_handle,
          "params": [self.id]
        })['result']['qReturn']['qHandle']
        logger.debug('Measure.get_handle function completed, %s', self.handle)
        return self.handle
    
    def update(self, definition = None, label = None, label_expression = None, description = None, format_type = None, \
               format_ndec = -1, format_use_thou = -1, format_dec = None, format_thou = None):
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
            if y is None:
                if str(x) == 'nan': return ''
                else: return str(x)
            elif type(y) == str:
                return str(y)
            elif y == -1: 
                if str(x) == 'nan': return 0
                else: return int(x)
            else: return int(y)
            
        definition, label, label_expression, description, format_type, format_ndec, format_use_thou, format_dec, format_thou = \
                                    gn(self.definition, definition),           \
                                    gn(self.label, label),                     \
                                    gn(self.label_expression, label_expression), \
                                    gn(self.description, description),         \
                                    gn(self.format_type, format_type),           \
                                    gn(self.format_ndec, format_ndec),           \
                                    gn(self.format_use_thou, format_use_thou),     \
                                    gn(self.format_dec, format_dec),             \
                                    gn(self.format_thou, format_thou)
        
        t = {
          "jsonrpc": "2.0",
          "id": 2,
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
                  }
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
                self.parent.df.loc[self.parent.df['qInfo.qId'] == self.id, 'qData.measure.qDef'] = definition
                self.parent.df.loc[self.parent.df['qInfo.qId'] == self.id, 'qData.measure.qLabel'] = label
                self.parent.df.loc[self.parent.df['qInfo.qId'] == self.id, 'qData.measure.qLabelExpression'] = label_expression
                self.parent.df.loc[self.parent.df['qInfo.qId'] == self.id, 'qMeta.description'] = description
                self.parent.df.loc[self.parent.df['qInfo.qId'] == self.id, 'qData.measure.qNumFormat.qType'] = format_type
                self.parent.df.loc[self.parent.df['qInfo.qId'] == self.id, 'qData.measure.qNumFormat.qnDec'] = format_ndec
                self.parent.df.loc[self.parent.df['qInfo.qId'] == self.id, 'qData.measure.qNumFormat.qUseThou'] = format_use_thou
                self.parent.df.loc[self.parent.df['qInfo.qId'] == self.id, 'qData.measure.qNumFormat.qDec'] = format_dec
                self.parent.df.loc[self.parent.df['qInfo.qId'] == self.id, 'qData.measure.qNumFormat.qThou'] = format_thou
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
        zu = query(self.parent.ws, {
              "jsonrpc": "2.0",
              "id": 10,
              "method": "DestroyMeasure",
              "handle": self.app_handle,
              "params": [
                self.id
              ]
            })
        
        # delete value from measures collection
        if zu['result']['qSuccess']:
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
          "id": 2,
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


# In[23]:

class Dimension:
    """
    The class, representing the master dimensions of the application
    Member of the App.dimensions collection
    """
    def __init__(self, parent, dimName):
        self.name = dimName
        self.handle = 0
        self.app_handle = 0
        self.parent = parent
        
        self.id, self.definition, self.label, self.label_expression = '', '', '', ''
        self.created_date, self.modified_date = dt.datetime(year=1901, month=1, day=1), dt.datetime(year=1901, month=1, day=1)
        
        
    def get_handle(self) -> int:
        """
        Get the handle of the dimension

        Returns:
            Handle of the dimension
        """
        logger.debug('Dimension.get_handle function started, name = %s', self.name)
        self.handle = query(self.parent.ws, {
          "jsonrpc": "2.0",
          "id": 4,
          "method": "GetDimension",
          "handle": self.app_handle,
          "params": [self.id]
        })['result']['qReturn']['qHandle']
        logger.debug('Dimension.get_handle function completed, name = %s', self.name)
        return self.handle
    
    def update(self, definition: Union[str, List[str]] = None, label: Union[str, List[str]] = None) -> bool:
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

        # if definition or labels are strings, convert them to lists
        if isinstance(definition, str): definition = [definition]
        if isinstance(label, str): label = [label]
        
        # check if new values are provided, otherwise use old ones
        def gn(x, y):
            if y is None: 
                if str(x) == 'nan': return []
                else: return x
            else: return y
            
        definition, label = \
            gn(self.definition, definition), \
            gn(self.label, label)

        t = {
          "jsonrpc": "2.0",
          "id": 2,
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
                  "qFieldDefs": definition
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
                row_label = self.parent.df.index[self.parent.df['qInfo.qId'] == self.id].tolist()[0]
                self.parent.df.at[row_label, 'qDimFieldDefs'] = definition
                self.parent.df.at[row_label, 'qDimFieldLabels'] = label
                
                logger.info('Dimension updated: %s, new definition: %s, new label: %s', self.name, self.definition, self.label)
                return True
        except Exception as E:
            logger.exception('Failed to update dimension: %s, Error: %s', self.name, str(E))
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
              "id": 10,
              "method": "DestroyDimension",
              "handle": self.app_handle,
              "params": [
                self.id
              ]
            })
        
        # delete value from dimensions collection
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
          "id": 2,
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


class Sheet:
    """
    The class, representing the sheets of the application
    Member of the App.sheets collection
    """

    def __init__(self, parent, sheetName):
        self.name = sheetName
        self.handle = 0
        self.parent = parent
        self.app_handle = parent.app_handle
        
        self.id = ''
        self.description = ''
        self.created_date = dt.datetime(year=1901, month=1, day=1)
        self.modified_date = dt.datetime(year=1901, month=1, day=1)
        self.published = ''
        self.approved = ''
        self.ownerId = ''
        self.ownerName = ''
        
        self.objects = SheetChildren(self)
        
    def get_handle(self) -> int:
        logger.debug('Sheet.get_handle function started, name = %s', self.name)
        self.handle = query(self.parent.ws, {
              "jsonrpc": "2.0",
              "id": 4,
              "method": "GetObject",
              "handle": self.app_handle,
              "params": [
                self.id
              ]
            })['result']['qReturn']['qHandle']
        logger.debug('Sheet.get_handle function finished, handle = %s', self.handle)
        return self.handle

    def load(self):
        # load sheet objects, a shotcut for SheetChildren.load()
        logger.debug('Sheet.load function started, name = %s', self.name)
        self.objects.load()

# In[27]:

class SheetChildren():
    """
    The class, representing the collection of the objects on the sheet
    """
    def __init__(self, parent):
        self.children = {}
        self.count = 0
        self.sheet_handle = 0
        self.app_handle = parent.app_handle
        self.parent = parent
        self.parentId = parent.id
        
        
    def __getitem__(self, childName):
        logger.debug('SheetChildren.__getitem__ started, name = %s', childName)
        
        
        return self.children[childName]
    
    def __setitem__(self, childName, var):
        logger.debug('SheetChildren.__setitem__ started, name = %s', childName)
        self.children[childName] = var
            
    def __delitem__(cls, childName):
        logger.debug('SheetChildren.__delitem__ started, name = %s', childName)
        del cls.children[childName]
        cls.count -= 1
            
    def __iter__(self):
        # initializing collection if empty
        logger.debug('SheetChildren.__iter__ started')
        if self.count == 0:
            self.load()
        return ChildrenIterator(self)
    
    def load(self):
        """
        Loads all sheer objects from Qlik Sense into the collection
        """
        logger.debug('SheetChildren.load started, %s', self.parent.name)
        if self.count == 0:
            self.sheet_handle = self.parent.get_handle()
            self.df = _get_sheet_objects_pandas(self.parent.parent.ws, self.sheet_handle)
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
                obj.boundsY = row['bounds.y']
                obj.boundsX = row['bounds.x']
                obj.boundsWidth = row['bounds.width']
                obj.boundsHeight = row['bounds.height']

                self[objName] = obj
                self.count += 1
        else:
            logger.warning('SheetChildren.load function, objects already loaded, recreate the App object to reload')

        logger.debug('SheetChildren.load finished, %s objects loaded', self.count)
    


# In[28]:

class Object:
    """
    The class, representing the objects on the sheet
    Member of the SheetChildren collection
    """
    def __init__(self, parent, objName):
        self.name = objName
        self.handle = 0
        self.parent = parent
        self.app_handle = parent.app_handle
        self.sheet_handle = parent.sheet_handle
        self.sheet = parent.parent
        
        self.type = ''
        self.col, self.row, self.colspan, self.rowspan, self.boundsY, self.boundsX, self.boundsWidth, self.boundsHeight = 0, 0, 0, 0, 0, 0, 0, 0
        
        self.dimensions = ObjectChildren(self, 'objectDimensions')
        self.measures = ObjectChildren(self, 'objectMeasures')
        
    def get_handle(self) -> int:
        """
        Returns handle of the object
        """

        logger.debug('Object.get_handle started, sheet = %s, name = %s, id = %s, app_handle = %s'\
                     , self.sheet.name, self.name, self.id, self.app_handle)
        self.handle = query(self.sheet.parent.ws, {
          "jsonrpc": "2.0",
          "id": 4,
          "method": "GetObject",
          "handle": self.app_handle,
          "params": [self.id]
        })['result']['qReturn']['qHandle']
        logger.debug('Object.get_handle finished, handle = %s', self.handle)
        return self.handle

    def load(self):
        """
        Loads object dimensions and measures from Qlik Sense
        """
        logger.debug('Object.load started, sheet = %s, name = %s, id = %s', self.sheet.name, self.name, self.id)
        self.get_handle()
        self.dimensions.load()
        self.measures.load()
        logger.debug('Object.load finished, dimensions = %s, measures = %s', \
                     self.dimensions.count, self.measures.count)
    


# In[29]:

class ObjectDimension():
    """
    The class, representing the dimensions, used in the object on the sheet
    Member of the ObjectChildren collection
    """

    def __init__(self, parent, dimName):
        self.name = dimName
        self.app_handle = 0
        self.parent = parent
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
                if str(x) == 'nan': return ''
                else: return x
            else: return y
            
        definition, label, calc_condition = \
            gn(self.definition, definition),                \
            gn(self.label, label),                          \
            gn(self.calc_condition, calc_condition)

        # receiving properties of parent object
        old_properties = query(self.object.sheet.parent.ws, {
              "jsonrpc": "2.0",
              "id": 4,
              "method": "GetProperties",
              "handle": self.object.handle,
              "params": []
            })['result']['qProp']
               
        # changing properties json
        try:
            old_properties['qHyperCubeDef']['qDimensions'][self.index]['qDef']['qFieldDefs'] = definition
            old_properties['qHyperCubeDef']['qDimensions'][self.index]['qDef']['qFieldLabels'] = label
            old_properties['qHyperCubeDef']['qDimensions'][self.index]['qCalcCondition']['qCond']['qv'] = calc_condition
        except Exception as E:
            logger.exception('Unable to change old properties of the dimension, error: %s', E)
            return False

        # setting new properties
        query_result = query(self.object.sheet.parent.ws, {
              "jsonrpc": "2.0",
              "id": 4,
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
        t = query(self.object.sheet.parent.ws, {
              "jsonrpc": "2.0",
              "id": 4,
              "method": "GetProperties",
              "handle": self.object.handle,
              "params": []
            })['result']['qProp']
               
        # deleting item properties json
        t['qHyperCubeDef']['qDimensions'].pop(self.index)
        t['qHyperCubeDef']['qInterColumnSortOrder'].remove(max(t['qHyperCubeDef']['qInterColumnSortOrder']))
        t['qHyperCubeDef']['qColumnOrder'].remove(max(t['qHyperCubeDef']['qColumnOrder']))
        t['qHyperCubeDef']['columnOrder'].remove(max(t['qHyperCubeDef']['columnOrder']))
        t['qHyperCubeDef']['columnWidths'].pop(self.index)   # здесь  неправильно - не ясно какую колонку на самом деле мы удаляем
        
        # setting new properties
        zu = query(self.object.sheet.parent.ws, {
              "jsonrpc": "2.0",
              "id": 4,
              "method": "SetProperties",
              "handle": self.object.handle,
              "params": [
                t
                ]
            })
        
        # delete value from variables collection
        
        if 'change' in zu:
            logger.info('ObjectDimension.delete, Dimension deleted: %s', self.name)
            del self.parent[self.name]
        else: logger.error('ObjectDimension.delete, Failed to delete dimension: %s', self.name)
        
        return zu


# In[30]:

class ObjectMeasure():
    """
    The class, representing the measures, used in the object on the sheet
    Member of the ObjectChildren collection
    """
    def __init__(self, parent, msName):
        self.name = msName
        self.app_handle = 0
        self.parent = parent
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
                if str(x) == 'nan': return ''
                else: return str(x)
            else: return str(y)
            
        # check if new values exists; if not, leave old values without change
        def fn(x, y):
            if y == -1: 
                if str(x) == 'nan': return 0
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
        old_properties = query(self.object.sheet.parent.ws, {
              "jsonrpc": "2.0",
              "id": 4,
              "method": "GetProperties",
              "handle": self.object.handle,
              "params": []
            })['result']['qProp']
               
        # changing properties json
        try:
            old_properties['qHyperCubeDef']['qMeasures'][self.index]['qDef']['qDef'] = definition
            old_properties['qHyperCubeDef']['qMeasures'][self.index]['qDef']['qLabel'] = label
            old_properties['qHyperCubeDef']['qMeasures'][self.index]['qDef']['qLabelExpression'] = label_expression
            old_properties['qHyperCubeDef']['qMeasures'][self.index]['qCalcCondition']['qCond']['qv'] = calc_condition
            old_properties['qHyperCubeDef']['qMeasures'][self.index]['qLibraryId'] = library_id
            old_properties['qHyperCubeDef']['qMeasures'][self.index]['qDef']['qNumFormat']['qType'] = format_type
            #old_properties['qHyperCubeDef']['qMeasures'][self.index]['qDef']['qNumFormat']['qnDec'] = format_ndec
            # it seems NDec (number of decimals) is not implemented correctly by Qlik Sense - 09.07.2023
            old_properties['qHyperCubeDef']['qMeasures'][self.index]['qDef']['qNumFormat']['qUseThou'] = format_use_thou
            old_properties['qHyperCubeDef']['qMeasures'][self.index]['qDef']['qNumFormat']['qDec'] = format_dec
            old_properties['qHyperCubeDef']['qMeasures'][self.index]['qDef']['qNumFormat']['qThou'] = format_thou
        except Exception as E:
            logger.exception('Unable to change old properties of the measure, error: %s', E) 
            return False
        
        # setting new properties
        query_result = query(self.object.sheet.parent.ws, {
              "jsonrpc": "2.0",
              "id": 4,
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
        t = query(self.object.sheet.parent.ws, {
              "jsonrpc": "2.0",
              "id": 4,
              "method": "GetProperties",
              "handle": self.object.handle,
              "params": []
            })['result']['qProp']
               
        # deleting item properties json
        t['qHyperCubeDef']['qMeasures'].pop(self.index)
        t['qHyperCubeDef']['qInterColumnSortOrder'].remove(max(t['qHyperCubeDef']['qInterColumnSortOrder']))
        t['qHyperCubeDef']['qColumnOrder'].remove(max(t['qHyperCubeDef']['qColumnOrder']))
        t['qHyperCubeDef']['columnOrder'].remove(max(t['qHyperCubeDef']['columnOrder']))
        t['qHyperCubeDef']['columnWidths'].pop(self.index)   # здесь  неправильно - не ясно какую колонку на самом деле мы удаляем
        
        # setting new properties
        zu = query(self.object.sheet.parent.ws, {
              "jsonrpc": "2.0",
              "id": 4,
              "method": "SetProperties",
              "handle": self.object.handle,
              "params": [
                t
                ]
            })
        
        # delete value from variables collection
        
        if 'change' in zu:
            logger.info('Measure deleted: %s', self.name)
            del self.parent[self.name]
        else: logger.error('Failed to delete measure: %s', self.name)
        
        return zu


# In[31]:

class ObjectChildren():
    """
    The class, representing different collections of sheet objects, like measures or dimensions
    """
    def __init__(self, parent, _type):
        self.children = {}
        self.count = 0
        self.parent = parent
        self.app_handle = parent.app_handle
        self._type = _type
        self.sheet = parent.sheet
        
    
    def __getitem__(self, childCaller):
        logger.debug('ObjectChildren.__getitem__ started, sheet = %s, childCaller = %s', self.sheet.name, childCaller)
        
                        
        if type(childCaller) == str:
            # we can call child by name or by index
            return self.children[childCaller]
        else:
            for ch in self.children.keys():
                logger.debug(self.children[ch].index)
                if self.children[ch].index == childCaller: return self.children[ch]
    
    def __setitem__(self, childCaller, var):
        logger.debug('ObjectChildren.__setitem__ started, childCaller = %s', childCaller)
        self.children[childCaller] = var
            
    def __delitem__(cls, childCaller):
        logger.debug('ObjectChildren.__delitem__ started, childCaller = %s', childCaller)
        del cls.children[childCaller]
        cls.count -= 1
            
    def __iter__(self):
        # initializing collection if empty
        # rewrite this part
        logger.debug('ObjectChildren.__iter__ started, %s, %s', self.parent.name, self._type)
        if self.count == 0:
            try: zvb = self['']
            except: 1
        return ChildrenIterator(self)
    
    def load(self) -> bool:
        """
        Loads object dimensions or measures from Qlik Sense
        """
        logger.debug('ObjectChildren.load started, sheet = %s, object = %s, _type = %s', self.sheet.name, self.parent.name, self._type)

        def pick(row, colName, _type = str):
            if colName in row.index:
                return row[colName]
            else: 
                if _type == str: return ''
                else: return 0

        if self.count == 0:
            if self._type == 'objectDimensions':
                self.parentHandle = self.parent.get_handle()
                self.df = _get_object_dim_pandas(self.parent.parent.parent.parent.ws, self.parentHandle)
                if len(self.df) == 0:
                    logger.debug('No dimensions found for object %s', self.parent.name)
                    return True
                # since some cId can be empty, we need to fill them with some values; qsea_id column marks those values
                mask = self.df['qDef.cId'].isnull()
                self.df['qDef.cId'] = self.df['qDef.cId'].apply(lambda x: str(uuid.uuid4()) if pd.isnull(x) else x)
                self.df.loc[mask, 'qsea_id'] = 1
                self.df['qsea_id'].fillna(0, inplace=True)

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

            if self._type == 'objectMeasures':
                self.parentHandle = self.parent.get_handle()
                logger.debug('parentHandle: %s', self.parentHandle)
                self.df = _get_object_ms_pandas(self.parent.parent.parent.parent.ws, self.parentHandle)
                if len(self.df) == 0:
                    logger.debug('No measures found for object %s', self.parent.name)
                    return True
                
                # since some cId can be empty, we need to fill them with some values; qsea_id column marks those values
                mask = self.df['qDef.cId'].isnull()
                self.df['qDef.cId'] = self.df['qDef.cId'].apply(lambda x: str(uuid.uuid4()) if pd.isnull(x) else x)
                self.df.loc[mask, 'qsea_id'] = 1
                self.df['qsea_id'].fillna(0, inplace=True)

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
        else:
            logger.warning('ObjectChildren.load function, %s already loaded, recreate the App object to reload', self._type)
            return False
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
            t = query({
                  "jsonrpc": "2.0",
                  "id": 4,
                  "method": "GetProperties",
                  "handle": self.parent.handle,
                  "params": []
                })['result']['qProp']
            
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
            
            # setting new properties
            zu = query({
                  "jsonrpc": "2.0",
                  "id": 4,
                  "method": "SetProperties",
                  "handle": self.parent.handle,
                  "params": [
                    t
                    ]
                })

            # to refine: change dataframe only in case of success
            self.definition = definition
            self.label = label
            self.label_expression = label_expression
            #self.calc_condition = calc_condition

            return [t, zu]
            
