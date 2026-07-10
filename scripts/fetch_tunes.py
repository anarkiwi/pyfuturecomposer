#!/usr/bin/env python3
"""Download Future Composer ``.sid`` test tunes into a gitignored cache.

These tunes are HVSC copyright works and are **never** committed to this repo
(see ``.gitignore``).  They are fetched on demand from a public HVSC mirror into
``tests/.tunecache/`` (gitignored), so a fresh clone works with no
machine-specific paths.  The byte-exact player tests skip when a tune is absent
(and CI has no network), mirroring how the register-log oracle test is env-gated.

The fetch / resolve mechanics are the shared :mod:`pysidtracker.testing` core;
this script keeps only the Future Composer corpus mapping and the CLI.

Usage::

    python scripts/fetch_tunes.py                # fetch every test tune
    python scripts/fetch_tunes.py --id werdabest # fetch one
    python scripts/fetch_tunes.py --list         # print id -> HVSC path
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path

from pysidtracker.testing import TuneFetchError, fetch_tune, resolve_tune

REPO = Path(__file__).resolve().parent.parent
CACHE = Path(os.environ.get("FC_TUNECACHE", str(REPO / "tests" / ".tunecache")))

# id -> HVSC relative path.  We R Da Best (tune 2) is the decompile reference
# (the tune the Future Composer player byte-exact validation was derived from).
TUNES = {
    "werdabest": "MUSICIANS/J/Jade_Tiger/We_R_Da_Best_tune_2.sid",
}


def fetch(relpath: str, *, force: bool = False) -> Path:
    """Fetch ``relpath`` from the HVSC mirror into the cache; return its path."""
    return fetch_tune(relpath, cache_dir=CACHE, force=force)


def fetch_id(tune_id: str, *, force: bool = False) -> Path:
    """Fetch the tune registered under ``tune_id``."""
    return fetch(TUNES[tune_id], force=force)


def resolve(relpath: str) -> Path:
    """Path to ``relpath`` from a local HVSC tree (``$HVSC``), the cache, or mirror.

    Raises :class:`~pysidtracker.testing.TuneFetchError` if the tune cannot be
    obtained anywhere (offline and uncached).
    """
    path = resolve_tune(relpath, cache_dir=CACHE)
    if path is None:
        raise TuneFetchError(f"{relpath}: unavailable (offline, not cached)")
    return path


def main(argv=None) -> int:
    """CLI entry point."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--id", help="only this tune id")
    parser.add_argument("--force", action="store_true", help="re-download")
    parser.add_argument("--list", action="store_true", help="print id -> path")
    args = parser.parse_args(argv)

    if args.list:
        for tid, rel in TUNES.items():
            print(f"{tid}\t{rel}")
        return 0

    ids = [args.id] if args.id else list(TUNES)
    for tid in ids:
        path = fetch_id(tid, force=args.force)
        print(f"{tid}: {TUNES[tid]} -> {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
