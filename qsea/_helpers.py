import json

from qsea._config import logger


def _test():
    const = 39
    logger.info('Test function completed, %s', const)
    return const


def _to_qlik(string):
    if string is None: return ""
    else: return json.dumps(str(string))


def _find_key(key, dictionary):
    if key in dictionary:
        return True
    for k, v in dictionary.items():
        if isinstance(v, dict):
            if _find_key(key, v):
                return True
    return False


def _build_set_modifier(filters: dict) -> str:
    """
    Builds a Qlik Set Analysis modifier string from a dict of filters.

    Args:
        filters (dict): field names -> values.
            Values can be int, float, str, or list of these types.

    Returns:
        str: Set Analysis modifier, e.g. '{<[Year]={2025},[City]={\"Moscow\"}>}'
    """
    if not filters:
        return ''

    parts = []
    for field, values in filters.items():
        if not isinstance(values, list):
            values = [values]
        formatted = []
        for v in values:
            if isinstance(v, str):
                formatted.append(f"'{v.replace(chr(39), chr(39)+chr(39))}'")
            else:
                formatted.append(str(v))
        parts.append(f'[{field}]={{{",".join(formatted)}}}')

    return '{<' + ','.join(parts) + '>}'
