# QSEA Publish Workflow

## Public Contract

The public installation path does not change during this migration:

```powershell
pip install qsea
```

`uv` is only the maintainer workflow and environment layer. The build backend remains `setuptools.build_meta`.

## Current State

The migration is complete at the workflow level:

- project metadata is centralized in `pyproject.toml`;
- release artifacts are built through `uv build`;
- old local `qsea_env` directories and manual legacy test scripts are no longer part of the supported workflow.

## Maintainer Workflow With uv

Use PowerShell 7 commands from the project root.

### 1. Sync the maintainer toolchain

```powershell
uv sync --group dev
```

This installs the project together with the build, test and publish tools used by the supported uv workflow.

### 2. Run the default validation suite

```powershell
uv run pytest tests/
```

Default pytest behavior:

- discovers the modular stable suite via `test_suite_*.py` plus `tests/test_packaging_config.py`;
- excludes `experimental` and `slow` tests by default;
- still runs the stable smoke and integration suite;
- skips live Qlik tests automatically when `QLIKSENSE_API_KEY` is not available.

### 3. Run a focused smoke check

```powershell
uv run pytest tests/test_suite_app_loading.py::test_package_smoke_check
```

### 4. Build the publish artifacts

```powershell
if (Test-Path build) { Remove-Item -Recurse -Force build }
if (Test-Path dist) { Remove-Item -Recurse -Force dist }
if (Test-Path qsea.egg-info) { Remove-Item -Recurse -Force qsea.egg-info }

uv build
uv run twine check dist/*
```

### 5. Smoke-install the built wheel in a temporary environment

```powershell
$smokeRoot = Join-Path $env:TEMP "qsea-publish-smoke"
if (Test-Path $smokeRoot) { Remove-Item -Recurse -Force $smokeRoot }

uv venv $smokeRoot
uv pip install --python (Join-Path $smokeRoot "Scripts/python.exe") (Get-ChildItem .\dist\qsea-*.whl).FullName
& (Join-Path $smokeRoot "Scripts/python.exe") -c "import qsea; print(qsea.__file__); print(qsea._test())"
```

## Validation Checklist

Before publishing, confirm the release candidate with the same checks:

- `import qsea` succeeds from the built wheel;
- `qsea._test()` returns the expected value;
- `Requires-Dist` contains only the expected runtime dependencies;
- long description still includes the intended README and history content;
- `LICENSE.txt`, `README.md`, `HISTORY.md` and the test suite are present in the source distribution;
- wheel metadata points to the correct homepage/download URLs and author metadata;
- `.venv/` stays out of `git status`.

Useful inspection commands:

```powershell
uv run python -c "import pathlib, zipfile; wheel = next(pathlib.Path('dist').glob('qsea-*.whl')); zf = zipfile.ZipFile(wheel); print(zf.read([n for n in zf.namelist() if n.endswith('METADATA')][0]).decode())"
uv run python -c "import pathlib, tarfile; sdist = next(pathlib.Path('dist').glob('qsea-*.tar.gz')); tf = tarfile.open(sdist); [print(name) for name in tf.getnames()]"
```

## 6. Publish to PyPI

After validation, upload to PyPI:

```powershell
uv run twine upload dist/*
```

For Test PyPI (recommended before first production upload):

```powershell
uv run twine upload --repository testpypi dist/*
```

**Requirements:**
- PyPI account: https://pypi.org/account/register/
- API token: Account Settings -> API tokens -> Add API token
- Configure credentials: `~/.pypirc` or environment variables `TWINE_USERNAME` / `TWINE_PASSWORD` (use `__token__` and the token value for password)

## Release Policy

The supported release path is now:

```powershell
uv build
uv run twine check dist/*
```

This is the only supported way to produce release artifacts for publication.

`uv build` is preferred not only for convenience, but because it produces the normalized wheel and source distribution that match the project packaging configuration.

## Rollback Triggers

Treat the release as blocked and fix the `uv` workflow before publishing if any of the following happens:

- wheel or sdist metadata diverges unexpectedly from the normalized baseline;
- `Requires-Dist` changes unexpectedly;
- wheel smoke install fails;
- source distribution is missing required files;
- validation runs different tests than the documented stable suite;
- `uv build`, `twine check`, or the publish upload path fails;
- local `.venv` state causes Windows file locks during `uv sync` or `uv run`, making the maintainer environment inconsistent.
