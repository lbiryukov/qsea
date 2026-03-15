from qsea._config import logger
from qsea._engine import _open_connection
from qsea._loaders import _get_app_list


class Connection:
    """
    The class that represents a dictionary of websocket connections to Qlik Sense Engine Api
    Since one websocket connection can be used only for one app, this class is used to handle all websocket connections
    New websocket connections are created automatically when a new app object is created
    """
    
    def __init__(self, header_user, qlik_url, timeout: int = 10, verify_ssl: bool = True):
        logger.debug('Connection class started')
        self.header_user = header_user
        self.qlik_url = qlik_url
        self.timeout = timeout
        self.verify_ssl = verify_ssl
        
        main_ws = _open_connection(qlik_url, header_user, timeout, verify_ssl=verify_ssl)
        
        self.main_app_id = None
        self.df = _get_app_list(main_ws)

        try:
            main_ws.close()
        except Exception:
            pass

        self.wss = {}
        self._closed = False

    def close(self):
        """
        Closes all secondary WebSocket connections.
        """
        logger.debug('Connection.close started')
        if self._closed:
            return
        self._closed = True
        for app_id, ws in self.wss.items():
            try:
                ws.close()
            except Exception as e:
                logger.warning('Error closing secondary WebSocket for app %s: %s', app_id, e)
        self.wss.clear()
        logger.info('Connection closed')

    def __del__(self):
        try:
            self.close()
        except Exception:
            pass

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
        return False

    def reload_app_list(self):
        """
        Reloads the list of apps, in case if new apps were added after the Connection object was created
        """
        tmp_ws = _open_connection(self.qlik_url, self.header_user, self.timeout, verify_ssl=self.verify_ssl)
        self.df = _get_app_list(tmp_ws)
        try:
            tmp_ws.close()
        except Exception:
            pass
