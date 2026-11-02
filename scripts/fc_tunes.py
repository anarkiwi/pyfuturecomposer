"""List the HVSC tunes the Future Composer format accepts, with their build flags.

``fc_tunes.py HVSC OUT.csv`` finds the tunes SIDId names MoN/FutureComposer, keeps those
:func:`pysidtracker.find_format` hands to this format, and writes ``path`` plus the
spec-visible build flags (``state``: the entry tests a play-state byte) per tune.
"""

import argparse
import csv
import tempfile
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

from tqdm import tqdm

PLAYER = "MoN/FutureComposer"


def probe(path):
    """``(path, flags)`` of an accepted tune, else None."""
    # pylint: disable=import-outside-toplevel
    from pysidtracker import find_format

    from pyfuturecomposer import layout

    try:
        raw = Path(path).read_bytes()
        fmt = find_format(raw)
        if fmt is None or fmt.name != "futurecomposer":
            return None
        song = fmt.parser.parse(raw)
        return path, {"state": int(layout.variant(song).resolve().state)}
    except Exception:  # pylint: disable=broad-exception-caught
        return None


def main() -> None:
    """Write the accepted tunes of an HVSC tree."""
    # pylint: disable=import-outside-toplevel
    from pysidtracker.survey import find

    parser = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    parser.add_argument("hvsc")
    parser.add_argument("out")
    parser.add_argument("--jobs", type=int, default=16)
    args = parser.parse_args()
    with tempfile.TemporaryDirectory() as tmp:
        listing = Path(tmp, "sidid.csv")
        find(args.hvsc, listing, player_regex=PLAYER, jobs=args.jobs)
        with open(listing, encoding="utf-8") as handle:
            rows = [r["path"] for r in csv.DictReader(handle) if r["player"] == PLAYER]
    paths = [str(Path(args.hvsc, p)) for p in rows]
    with ProcessPoolExecutor(args.jobs) as pool:
        found = [
            r for r in tqdm(pool.map(probe, paths, chunksize=16), total=len(paths)) if r
        ]
    with open(args.out, "w", newline="", encoding="utf-8") as handle:
        out = csv.writer(handle)
        out.writerow(["path", "state"])
        out.writerows((path, flags["state"]) for path, flags in sorted(found))
    print(len(found), "of", len(paths), "accepted")


if __name__ == "__main__":
    main()
