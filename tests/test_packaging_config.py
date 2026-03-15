from __future__ import annotations

import tomllib
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


def load_pyproject() -> dict:
    with (ROOT / "pyproject.toml").open("rb") as fh:
        return tomllib.load(fh)


def test_project_metadata_is_centralized_in_pyproject():
    project = load_pyproject()["project"]

    assert project["name"] == "qsea"
    assert project["version"] == "1.1.0"
    assert project["dynamic"] == ["readme"]
    assert project["dependencies"] == ["pandas", "websocket-client"]
    assert project["authors"] == [{"name": "Lev Biriukov", "email": "lbiryukov@gmail.com"}]
    assert project["urls"]["Homepage"] == "https://github.com/lbiryukov/qsea"
    assert project["urls"]["Download"] == "https://pypi.org/project/qsea/"


def test_dev_dependency_group_covers_publish_toolchain():
    dev_group = load_pyproject()["dependency-groups"]["dev"]

    assert any(dep.startswith("build") for dep in dev_group)
    assert any(dep.startswith("pytest") for dep in dev_group)
    assert any(dep.startswith("setuptools") for dep in dev_group)
    assert any(dep.startswith("twine") for dep in dev_group)
    assert any(dep.startswith("wheel") for dep in dev_group)


def test_pytest_defaults_cover_all_test_modules():
    pytest_cfg = load_pyproject()["tool"]["pytest"]["ini_options"]

    assert pytest_cfg["testpaths"] == ["tests"]
    assert pytest_cfg["python_files"] == ["test_suite_*.py", "test_packaging_config.py", "test_unit_*.py"]
    assert pytest_cfg["addopts"] == '-ra -m "not experimental and not slow"'


def test_setuptools_package_discovery_excludes_tests_from_wheel():
    setuptools_cfg = load_pyproject()["tool"]["setuptools"]
    package_find = setuptools_cfg["packages"]["find"]

    assert setuptools_cfg["include-package-data"] is False
    assert package_find["include"] == ["qsea*"]
    assert package_find["exclude"] == ["tests*"]
