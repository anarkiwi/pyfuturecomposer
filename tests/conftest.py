"""Shared test fixtures: HVSC tune access.

Tunes are HVSC copyright works, never committed.  ``tune_path`` (from the shared
:func:`pysidtracker.testing.make_tune_fixtures`) fetches a tune into
pysidtracker's tune cache, skipping the test when the tune is absent and there is
no network.  The byte-exact ground truth comes from the shared sidtrace Docker
oracle -- see ``tests/test_oracle_hvsc.py`` (marked ``oracle``).
"""

import sys
from pathlib import Path

from pysidtracker.testing import make_tune_fixtures

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

# id -> HVSC relative path.  We R Da Best (tune 2) is the decompile reference
# (the tune the Future Composer player byte-exact validation was derived from).
TUNES = {
    "werdabest": "MUSICIANS/J/Jade_Tiger/We_R_Da_Best_tune_2.sid",
}

tune_id, tune_path = make_tune_fixtures(TUNES)
