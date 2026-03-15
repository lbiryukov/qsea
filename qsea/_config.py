import logging
from pathlib import Path


class Config:
    def __init__(self) -> None:
        self.logQueryMaxLength = 300


logger = logging.getLogger("qsea")
logger.addHandler(logging.NullHandler())
config = Config()


def setup_logging(log_file_path=None, log_level=logging.INFO, log_format=None):
    """Configure logging for the qsea library.

    Without arguments, adds a StreamHandler (stderr).
    With *log_file_path*, adds a FileHandler (append mode) and auto-creates
    parent directories when they don't exist.
    """
    if log_format is None:
        log_format = '%(asctime)s\t%(name)s\t%(funcName)s()\t%(levelname)s: %(message)s'

    formatter = logging.Formatter(log_format)
    qsea_logger = logging.getLogger("qsea")
    qsea_logger.setLevel(log_level)

    if log_file_path:
        Path(log_file_path).parent.mkdir(parents=True, exist_ok=True)
        handler = logging.FileHandler(log_file_path, mode="a", encoding="utf-8")
    else:
        handler = logging.StreamHandler()

    handler.setFormatter(formatter)
    qsea_logger.addHandler(handler)
