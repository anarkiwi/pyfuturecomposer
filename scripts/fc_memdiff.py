"""Run FutureComposerPlayer beside the tune's own 6502 code and report divergence.

``fc_memdiff.py tune.sid`` prints its first diverging frames; ``fc_memdiff.py
tunes.csv --hvsc $HVSC`` groups a survey find CSV by first diverging work byte.
"""

import argparse
import csv
import os
from collections import Counter
from concurrent.futures import ProcessPoolExecutor

from pysidtracker.oracle import EmuPlayer
from tqdm import tqdm

from pyfuturecomposer import FutureComposerPlayer, constants, read


def diverge(song, frames: int, subtune: int = 0, limit: int = 4, progress=True):
    """Yield ``(frame, regs, work)`` for the first ``limit`` diverging frames."""
    lib = FutureComposerPlayer(song, subtune)
    emu = EmuPlayer(song.image, song.load, song.init, song.play, subtune)
    base = lib.variant["work"]
    span = range(base, base + constants.WORK_SIZE)
    for frame in tqdm(range(frames), unit="frame", disable=not progress):
        lib.play_frame()
        emu.play_frame()
        regs = [r for r, (a, b) in enumerate(zip(lib.regs, emu.regs)) if a != b]
        work = {
            constants.WORK_BASE + a - base: (lib._rd(a), emu._rd(a))
            for a in span
            if lib._rd(a) != emu._rd(a)
        }
        if regs or work:
            yield frame, regs, work
            limit -= 1
            if not limit:
                return


def first_divergence(job):
    """``(path, (cause, frame))``: the first diverging work byte or register."""
    path, frames = job
    try:
        for frame, regs, work in diverge(read(path), frames, limit=1, progress=False):
            cause = f"${min(work):04x}" if work else f"reg {regs[0]}"
            return path, (cause, frame)
    except Exception as exc:  # pylint: disable=broad-exception-caught
        return path, (type(exc).__name__, 0)
    return path, ("exact", frames)


def batch(tunes, hvsc, frames: int, jobs: int) -> None:
    """Print the first-divergence causes of every tune in a ``find`` CSV."""
    with open(tunes, newline="", encoding="utf-8") as f:
        paths = [os.path.join(hvsc, row["path"]) for row in csv.DictReader(f)]
    causes, example = Counter(), {}
    with ProcessPoolExecutor(jobs) as pool:
        done = pool.map(first_divergence, [(p, frames) for p in paths], chunksize=4)
        for path, (cause, frame) in tqdm(done, total=len(paths), unit="tune"):
            causes[cause] += 1
            example.setdefault(cause, (os.path.relpath(path, hvsc), frame))
    for cause, count in causes.most_common():
        rel, frame = example[cause]
        print(f"{count:6d} {cause:12s} e.g. {rel} @ frame {frame}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("tune", help="a .sid/.prg, or a survey find CSV")
    parser.add_argument("--frames", type=int, default=500)
    parser.add_argument("--subtune", type=int, default=0)
    parser.add_argument("--hvsc", default=os.environ.get("HVSC", ""))
    parser.add_argument("--jobs", type=int, default=os.cpu_count())
    args = parser.parse_args()
    if args.tune.endswith(".csv"):
        batch(args.tune, args.hvsc, args.frames, args.jobs)
        return
    for frame, regs, work in diverge(read(args.tune), args.frames, args.subtune):
        cells = " ".join(f"${a:04x}={x:02x}/{y:02x}" for a, (x, y) in work.items())
        print(f"frame {frame}: regs {regs} work(lib/emu) {cells}")


if __name__ == "__main__":
    main()
