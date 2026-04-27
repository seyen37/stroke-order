"""Shared pytest fixtures."""
from pathlib import Path

import pytest

from stroke_order.sources.g0v import G0VSource


FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture(scope="session")
def source() -> G0VSource:
    """Network-disabled G0V source reading from tests/fixtures/."""
    return G0VSource(cache_dir=FIXTURES_DIR, allow_network=False)
