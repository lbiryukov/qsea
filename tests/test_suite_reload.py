from __future__ import annotations

import pytest

from ._integration_helpers import MAIN_APP_NAME


pytestmark = [pytest.mark.integration]


def test_reload_data_completes_successfully(app_factory):
    app = app_factory(app_name=MAIN_APP_NAME, load=False)
    app.reload_data()


def test_app_is_usable_after_reload(app_factory):
    app = app_factory()
    assert app.variables.count > 0, "No variables loaded after reload"
    assert app.measures.count > 0, "No measures loaded after reload"
