"""Shared test fixtures: HVSC tune access.

Tunes are HVSC copyright works, never committed.  ``tune_path`` (from the shared
:func:`pysidtracker.testing.make_tune_fixtures`) fetches a tune into a gitignored
cache, skipping the test when the tune is absent and there is no network.  The
byte-exact ground truth now comes from the shared sidtrace Docker oracle -- see
``tests/test_oracle_hvsc.py`` (marked ``oracle``).
"""

import sys
from pathlib import Path

from pysidtracker.testing import make_tune_fixtures

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))

import fetch_tunes  # noqa: E402  (after sys.path tweak)

# Parametrized ``tune_id`` + skipping ``tune_path`` fixtures over the FC corpus.
tune_id, tune_path = make_tune_fixtures(fetch_tunes.TUNES, fetch_tunes.CACHE)
