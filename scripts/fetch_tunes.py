#!/usr/bin/env python3
"""Download Future Composer ``.sid`` test tunes into a gitignored cache.

These tunes are HVSC copyright works and are **never** committed to this repo
(see ``.gitignore``).  They are fetched on demand from a public HVSC mirror into
``tests/.tunecache/`` (gitignored), so a fresh clone works with no
machine-specific paths.  The byte-exact player tests skip when a tune is absent
(and CI has no network), mirroring how the register-log oracle test is env-gated.

Usage::

    python scripts/fetch_tunes.py                # fetch every test tune
    python scripts/fetch_tunes.py --id werdabest # fetch one
    python scripts/fetch_tunes.py --list         # print id -> HVSC path
"""

from __future__ import annotations

import argparse
import os
import urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
CACHE = Path(os.environ.get("FC_TUNECACHE", str(REPO / "tests" / ".tunecache")))

# Public HVSC mirror.  Override with ``$HVSC_MIRROR``.
MIRROR = os.environ.get("HVSC_MIRROR", "https://hvsc.brona.dk/HVSC/C64Music").rstrip(
    "/"
)

# id -> HVSC relative path.  We R Da Best (tune 2) is the decompile reference
# (the tune the Future Composer player byte-exact validation was derived from).
TUNES = {
    "werdabest": "MUSICIANS/J/Jade_Tiger/We_R_Da_Best_tune_2.sid",
}


def _is_sid(data: bytes) -> bool:
    return data[:4] in (b"PSID", b"RSID")


def fetch(relpath: str, *, force: bool = False) -> Path:
    """Fetch ``relpath`` from the HVSC mirror into the cache; return its path."""
    relpath = relpath.lstrip("/")
    dest = CACHE / relpath
    if dest.exists() and not force:
        return dest
    url = f"{MIRROR}/{relpath}"
    req = urllib.request.Request(
        url, headers={"User-Agent": "pyfuturecomposer/fetch_tunes"}
    )
    with urllib.request.urlopen(req, timeout=60) as resp:  # nosec B310 (https mirror)
        data = resp.read()
    if not _is_sid(data):
        raise RuntimeError(f"{url}: not a SID file (magic {data[:4]!r})")
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(data)
    return dest


def fetch_id(tune_id: str, *, force: bool = False) -> Path:
    """Fetch the tune registered under ``tune_id``."""
    return fetch(TUNES[tune_id], force=force)


def resolve(relpath: str) -> Path:
    """Path to ``relpath`` from a local HVSC tree, the cache, or the mirror.

    Prefers a local HVSC checkout (``$HVSC``, e.g. ``.../C64Music``) so the
    corpus test runs for real against a present tree; otherwise falls back to
    the gitignored cache / the public mirror (``fetch``).  Raises if the tune
    cannot be obtained anywhere.
    """
    relpath = relpath.lstrip("/")
    hvsc = os.environ.get("HVSC")
    if hvsc:
        local = Path(hvsc) / relpath
        if local.exists():
            return local
    cached = CACHE / relpath
    if cached.exists():
        return cached
    return fetch(relpath)


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
