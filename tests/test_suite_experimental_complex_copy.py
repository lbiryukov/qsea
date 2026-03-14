from __future__ import annotations

import pytest


pytestmark = [
    pytest.mark.integration,
    pytest.mark.experimental,
    pytest.mark.skip(reason="Exploratory container/subitems scenarios are kept outside the stable suite."),
]


def test_container_sheet_copy_preserves_nested_subitems():
    pass


def test_get_child_infos_matches_between_source_and_target_objects():
    pass
