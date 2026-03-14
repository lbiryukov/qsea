# Структура проекта QSEA

Дата фиксации: 13/03/2026

## Кратко

QSEA — Python-пакет для работы с Qlik Sense Engine API. Основной код библиотеки по-прежнему сосредоточен в `qsea/__init__.py`, а packaging-конфигурация теперь централизована в `pyproject.toml` с `setuptools.build_meta` как build backend.

## Актуальное дерево проекта

```text
QSEA/
├─ .venv/                     # локальное окружение разработки через uv, в git не коммитится
├─ docs/
│  └─ publish_workflow.md     # maintainer workflow и release policy
├─ logs/                      # pytest и integration-логи
├─ qsea/
│  └─ __init__.py             # основной модуль библиотеки
├─ tests/
│  ├─ conftest.py
│  ├─ _integration_helpers.py
│  ├─ test_packaging_config.py
│  └─ test_suite_*.py
├─ build/                     # промежуточные артефакты сборки
├─ dist/                      # собранные wheel/sdist артефакты
├─ qsea.egg-info/             # локальные packaging metadata артефакты
├─ .gitignore
├─ HISTORY.md
├─ LICENSE.txt
├─ MANIFEST.in
├─ PROJECT_STRUCTURE.md
├─ README.md
├─ pyproject.toml
└─ uv.lock
```

## Назначение основных элементов

- `qsea/` — пакет библиотеки, устанавливаемый пользователям.
- `qsea/__init__.py` — основной исходный код проекта.
- `tests/` — pytest-набор для smoke, integration и slow-сценариев.
- `docs/publish_workflow.md` — внутренняя документация по publish-flow и release policy.
- `pyproject.toml` — источник истины для project metadata, зависимостей, pytest-конфигурации и uv dev toolchain.
- `MANIFEST.in` — состав source distribution.
- `uv.lock` — lock-файл зависимостей для uv workflow.
- `.venv/` — локальное окружение разработки; должно оставаться вне git.
- `build/`, `dist/`, `qsea.egg-info/` — генерируемые артефакты сборки и упаковки.
- `logs/` — runtime и test logs.

## Важные замечания

- В корне проекта есть `pyproject.toml`, и именно он определяет основной packaging workflow.
- Публичная установка для пользователей не меняется: `pip install qsea`.
- Основной release workflow выполняется через `uv build`, а build backend остаётся `setuptools.build_meta`.
