"""Count the frames a native player hands back to Python, over a tune list.

``fc_native.py TUNES.csv [--frames N] [--jobs J]`` plays every tune of a ``path`` CSV with
the format's native spec player and prints the tunes that bailed, with whether they
play on natively afterwards; the exit status is the number that ended in Python.
"""

import argparse
import csv
import sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

from tqdm import tqdm


def bails(job):
    """``(path, bails, native, error)`` after ``frames`` frames of a native player."""
    path, frames = job
    # pylint: disable=import-outside-toplevel
    from pysidtracker import find_format

    try:
        raw = Path(path).read_bytes()
        fmt = find_format(raw)
        player = fmt.spec_player(fmt.parser.parse(raw), native=True)
        player.render_grid(frames)
        return path, player._bails, player._fast, ""  # pylint: disable=protected-access
    except Exception as exc:  # pylint: disable=broad-exception-caught
        return path, 0, True, f"{type(exc).__name__}: {str(exc)[:80]}"


def main() -> int:
    """Print the tunes that left the native player."""
    parser = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    parser.add_argument("tunes")
    parser.add_argument("--frames", type=int, default=600)
    parser.add_argument("--jobs", type=int, default=16)
    args = parser.parse_args()
    with open(args.tunes, encoding="utf-8") as handle:
        paths = [row["path"] for row in csv.DictReader(handle)]
    python = 0
    with ProcessPoolExecutor(args.jobs) as pool:
        for path, count, native, error in tqdm(
            pool.map(bails, [(p, args.frames) for p in paths], chunksize=8),
            total=len(paths),
            unit="tune",
        ):
            python += not native and not error
            if count or error:
                print(Path(path).name, count, "native" if native else "python", error)
    print("tunes ending in python:", python, "of", len(paths))
    return python


if __name__ == "__main__":
    sys.exit(main())
