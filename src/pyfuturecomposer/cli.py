"""Command line interface: song info, register logs, and WAV rendering."""

import argparse
import sys

from pysidtracker.cli import add_reglog_command, add_wav_command, run_cli

from pyfuturecomposer import audio, reglog, writer
from pyfuturecomposer.errors import FutureComposerError
from pyfuturecomposer.reader import read

_SONG_HELP = "Future Composer .sid/.prg file"


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


def _export(args) -> None:
    song = read(args.song)
    fmt = args.format or ("sid" if args.output.lower().endswith(".sid") else "prg")
    if fmt == "sid":
        writer.write_sid(song, args.output)
    else:
        writer.write_prg(song, args.output)
    print(f"wrote {args.output} ({fmt})")
    if fmt == "prg" and not writer.is_editor_native(song):
        print(
            f"note: load ${song.load:04X} play ${song.play:04X} is a relocated rip; "
            "the FutureComposer editor loads the canonical $1800/$1806 build",
            file=sys.stderr,
        )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="pyfuturecomposer", description="Future Composer song tools"
    )
    commands = parser.add_subparsers(dest="command", required=True)

    info = commands.add_parser("info", help="print song metadata")
    info.add_argument("song", help=_SONG_HELP)
    info.set_defaults(func=_info)

    add_reglog_command(commands, _reglog, song_help=_SONG_HELP)
    add_wav_command(commands, _wav, song_help=_SONG_HELP)

    export = commands.add_parser(
        "export", help="write a form the FutureComposer editor can load"
    )
    export.add_argument("song", help=_SONG_HELP)
    export.add_argument("output", help="output file (.prg editor module or .sid)")
    export.add_argument(
        "--format",
        choices=("prg", "sid"),
        default=None,
        help="output format (default: inferred from the output extension)",
    )
    export.set_defaults(func=_export)
    return parser


def main(argv=None) -> int:
    """CLI entry point; returns a process exit code."""
    return run_cli(_parser, FutureComposerError, argv)


if __name__ == "__main__":
    sys.exit(main())
