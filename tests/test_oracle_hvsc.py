"""Byte-exact comparison of the FutureComposerPlayer render against the oracle.

Marked ``oracle``: these tests need Docker (the ``anarkiwi/sidtrace`` image) and
network access to HVSC, so the default suite excludes them (see ``pyproject``); a
dedicated CI job runs ``pytest -m oracle``.  They are never skipped -- an
unavailable tune or a failed oracle render fails the test rather than hiding a
regression.  HVSC ``.sid`` files are copyright works: they are downloaded to a
cache (or a local ``$HVSC`` tree), never committed.

The reusable ``pysidtracker.make_oracle_fixtures`` renders each tune with the FC
player and asserts the per-frame SID register grid matches the sidtrace
``sidplayfp`` oracle frame for frame (see ``docs/oracle-testing.md``).
"""

import os
from pathlib import Path

import pytest

from pysidtracker import make_oracle_fixtures

from pyfuturecomposer import FutureComposerPlayer

# Cache under the workspace (a Docker-daemon-visible path, and what CI persists
# via actions/cache).  ``$PYSIDTRACKER_ORACLE_CACHE`` overrides the location.
_CACHE = Path(os.environ.get("PYSIDTRACKER_ORACLE_CACHE", ".oracle-cache"))

# HVSC Future Composer tunes verified to render byte-exactly against the
# deterministic sidtrace oracle.  The FC playroutine here is a faithful
# transcription of ONE MoN/FutureComposer player build -- the one derived from
# ``We_R_Da_Best (tune 2)`` (the decompile reference) -- so byte-exact playback
# is confirmed for tunes carrying that build.  Recognition of the broader FC
# family (both player-code signatures, every load address, PSID + RSID) is
# covered separately by ``tests/test_corpus.py``.
TUNES = {
    "werdabest": "MUSICIANS/J/Jade_Tiger/We_R_Da_Best_tune_2.sid",
}


def _render(data, nframes):
    return FutureComposerPlayer(data).render_grid(nframes)


tune_id, oracle_match = make_oracle_fixtures(
    TUNES,
    hvsc_cache=_CACHE / "hvsc",
    oracle_cache=_CACHE / "csv",
    render=_render,
    frames=250,
)


@pytest.mark.oracle
def test_render_matches_oracle(oracle_match):  # noqa: F811
    oracle_match()
