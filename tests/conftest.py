import shutil

import pytest

from .utils import SNAPSHOT_DIR


@pytest.fixture(scope="session", autouse=True)
def clear_snapshots():
    if SNAPSHOT_DIR.exists():
        shutil.rmtree(SNAPSHOT_DIR)
