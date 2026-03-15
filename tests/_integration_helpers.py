from __future__ import annotations

import uuid


QLIK_URL = "wss://co-qlik.eksmo-office.ru/pyt/app/"
MAIN_APP_NAME = "Qlik Engine Test"
TARGET_APP_NAME = "Qlik Engine Test Target"

RATING_SHEET_NAME = "Рейтинг розничных продаж книг"
RATING_OBJECT_ID = "19a714fc-2d34-4bc2-847f-f46ad8261202"
FORMATS_SHEET_NAME = "Разные форматы мер"
FORMATS_OBJECT_ID = "c77098bc-c76c-4f73-85a1-22ed0a8b92de"
VISUALS_SHEET_NAME = "Разные визуализации"
EXPORT_OBJECT_ID = "HZjgsYp"
FILTER_OBJECT_ID = "8350a777-28bc-4db2-9ec4-e797ef346863"
BOOKMARK_NAME = "Test Bookmark"

COPY_OBJECT_SOURCE_SHEET = "Исходный лист для копирования объектов"
COPY_OBJECT_TARGET_SHEET = "Целевой лист для копирования объектов"
COPY_OBJECT_SOURCE_ID = "KMTPzn"
COPY_SHEET_SOURCE_NAME = "Исходный лист для копирования листа"
COPY_SHEET_OBJECT_ID = "79c1a67d-a1e5-4bda-b65e-9bce6827b2ca"
COPY_SHEET_MEASURE_NAME = "Мастер-мера для проверки копирования листов"


def make_unique_name(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:10]}"


def get_item_or_false(collection, key):
    try:
        return collection[key]
    except Exception:
        return False


def register_child_cleanup(cleanup_registry, app_factory, app_name: str, collection_name: str, item_name: str) -> None:
    def _cleanup() -> None:
        app = app_factory(app_name=app_name, load=False)
        collection = getattr(app, collection_name)
        collection.load()
        item = get_item_or_false(collection, item_name)
        if not item:
            return
        try:
            item.delete()
        except Exception:
            return
        try:
            app.save()
        except Exception:
            pass

    cleanup_registry.append(_cleanup)


def register_sheet_cleanup(cleanup_registry, app_factory, app_name: str, sheet_name: str) -> None:
    def _cleanup() -> None:
        app = app_factory(app_name=app_name, load=False)
        app.sheets.load()
        sheet = get_item_or_false(app.sheets, sheet_name)
        if not sheet:
            return
        try:
            sheet.delete()
        except Exception:
            return
        try:
            app.save()
        except Exception:
            pass

    cleanup_registry.append(_cleanup)


def get_first_field_with_value(app):
    """Return (field_name, value) for the first field that has at least one value."""
    import qsea
    field_name = list(app.fields.children.keys())[0]
    values = qsea._get_field_values(app.ws, app.handle, field_name)
    if not values:
        return None, None
    return field_name, next(iter(values))


def register_sheet_clear_cleanup(cleanup_registry, app_factory, app_name: str, sheet_name: str) -> None:
    def _cleanup() -> None:
        app = app_factory(app_name=app_name, load=False)
        app.sheets.load()
        sheet = get_item_or_false(app.sheets, sheet_name)
        if not sheet:
            return
        try:
            sheet.clear()
        except Exception:
            return
        try:
            app.save()
        except Exception:
            pass

    cleanup_registry.append(_cleanup)
