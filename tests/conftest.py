"""Shared test fixtures: tune access and the byte-exact oracle.

Tunes are HVSC copyright works, never committed.  ``tune_path`` (from the shared
:func:`pysidtracker.testing.make_tune_fixtures`) fetches a tune into a gitignored
cache, skipping the test when the tune is absent and there is no network.
``oracle_grid`` produces the ground-truth per-frame SID register grid -- live from
the ``preframr-sidtrace`` binary (``$SIDTRACE_BIN``) via the shared
:func:`pysidtracker.oracle.grid_from_writes` framer when available, else from the
committed frozen grid -- mirroring deplayroutine's env-gated validator.
"""

import os
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

from pysidtracker.oracle import grid_from_writes, read_sidwr
from pysidtracker.testing import make_tune_fixtures

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))

import fetch_tunes  # noqa: E402  (after sys.path tweak)

FIXTURES = Path(__file__).resolve().parent / "fixtures"

# Parametrized ``tune_id`` + skipping ``tune_path`` fixtures over the FC corpus.
tune_id, tune_path = make_tune_fixtures(fetch_tunes.TUNES, fetch_tunes.CACHE)


def _live_grid(tune, nframes=400):
    binary = os.environ.get("SIDTRACE_BIN")
    if not binary or not os.path.exists(binary):
        return None
    with tempfile.TemporaryDirectory() as tmp:
        prefix = os.path.join(tmp, "trace")
        subprocess.run(
            [binary, str(tune), "0", str(nframes), prefix],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return grid_from_writes(read_sidwr(prefix + ".sidwr.bin"))


def _frozen_grid(name):
    path = FIXTURES / f"{name}.grid.txt"
    if not path.exists():
        return None
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        rows.append([int(tok, 16) for tok in line.split()])
    return rows


@pytest.fixture
def oracle_grid(tune_id, tune_path):  # pylint: disable=redefined-outer-name
    """Ground-truth grid: live sidtrace if available, else the frozen grid."""
    grid = _live_grid(tune_path)
    source = "live-sidtrace"
    if grid is None:
        grid = _frozen_grid(tune_id)
        source = "frozen-grid"
    if grid is None:
        pytest.skip(f"no oracle for {tune_id}")
    return grid, source
