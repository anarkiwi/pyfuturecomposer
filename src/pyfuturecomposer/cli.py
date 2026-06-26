"""Command line interface: song info, register logs, and WAV rendering."""

import argparse
import sys

from pyfuturecomposer import audio, reglog
from pyfuturecomposer.errors import FutureComposerError
from pyfuturecomposer.reader import read


def _info(args) -> None:
    song = read(args.song)
    print(f"name:        {song.name}")
    print(f"author:      {song.author}")
    print(f"released:    {song.released}")
    print(f"load:        ${song.load:04X}")
    print(f"init/play:   ${song.init:04X} / ${song.play:04X}")
    print(f"image bytes: {len(song.image)}")


def _reglog(args) -> None:
    song = read(args.song)
    frames = round(args.seconds * 50)
    writes = reglog.iter_register_writes(song, max_frames=frames)
    reglog.write_reglog(writes, args.output)
    print(f"wrote {args.output}")


def _wav(args) -> None:
    song = read(args.song)
    audio.render_wav(song, args.output, seconds=args.seconds, model=args.model)
    print(f"wrote {args.output}")


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="pyfuturecomposer", description="Future Composer song tools"
    )
    commands = parser.add_subparsers(dest="command", required=True)

    info = commands.add_parser("info", help="print song metadata")
    info.add_argument("song", help="Future Composer .sid/.prg file")
    info.set_defaults(func=_info)

    log = commands.add_parser("reglog", help="write a SID register log")
    log.add_argument("song", help="Future Composer .sid/.prg file")
    log.add_argument("output", help="register log file to write")
    log.add_argument("--seconds", type=float, default=60.0)
    log.set_defaults(func=_reglog)

    wav = commands.add_parser("wav", help="render through an emulated SID")
    wav.add_argument("song", help="Future Composer .sid/.prg file")
    wav.add_argument("output", help="WAV file to write")
    wav.add_argument("--seconds", type=float, default=60.0)
    wav.add_argument("--model", choices=audio.CHIP_MODELS, default="8580")
    wav.set_defaults(func=_wav)
    return parser


def main(argv=None) -> int:
    """CLI entry point; returns a process exit code."""
    args = _parser().parse_args(argv)
    try:
        args.func(args)
    except (FutureComposerError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
