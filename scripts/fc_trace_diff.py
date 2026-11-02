"""Show where a tune's spec output first leaves a recorded reference.

``fc_trace_diff.py REF.pkl.gz TUNE.sid [--spec SPEC.play] [--context N]`` plays the tune with
the format's spec (or SPEC) and prints the SID writes of the first call whose audible registers
differ from the ``spec_trace.py record`` reference, with the calls before it.
"""

import argparse
import dataclasses
import gzip
import pickle
from pathlib import Path

from pysidtracker import find_format
from pysidtracker.playspec import load


def main() -> None:
    """Print the first differing call of one tune."""
    parser = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    parser.add_argument("ref")
    parser.add_argument("tune")
    parser.add_argument("--spec")
    parser.add_argument("--context", type=int, default=1)
    args = parser.parse_args()
    with gzip.open(args.ref, "rb") as handle:
        ref = pickle.load(handle)[str(Path(args.tune).resolve())]
    raw = Path(args.tune).read_bytes()
    fmt = find_format(raw)
    if args.spec:
        alt = load(args.spec)
        fmt = dataclasses.replace(
            fmt, spec=lambda m, f=fmt: dataclasses.replace(f.spec(m), spec=alt)
        )
    player = fmt.spec_player(fmt.parser.parse(raw), native=False)
    for call, (writes, regs) in enumerate(ref):
        player.play_frame()
        if tuple(player.snapshot()) != regs:
            print("call", call)
            print("reference", writes)
            print("got      ", tuple(player.writes))
            print("reference regs", regs)
            print("got       regs", tuple(player.snapshot()))
            return
    print("no difference")


if __name__ == "__main__":
    main()
