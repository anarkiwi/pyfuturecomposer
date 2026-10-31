"""Register Future Composer with the generic ``pysidtracker`` command-line tool.

:data:`FORMAT` on the ``pysidtracker.formats`` entry-point group makes
``pysidtracker info|reglog|wav`` play Future Composer tunes through
:class:`~pyfuturecomposer.reader.FutureComposerSidParser` and
:class:`~pyfuturecomposer.player.FutureComposerPlayer`, and contributes the
``export`` subcommand (an editor-loadable ``.prg`` or a PSID re-wrap); its ``spec``
hook exports the playspec.
"""

from __future__ import annotations

import sys
from typing import Iterable, Sequence

from pysidtracker import FormatCommand, SidFormat

from pyfuturecomposer import layout, writer
from pyfuturecomposer.model import Song
from pyfuturecomposer.player import FutureComposerPlayer, spec_binding
from pyfuturecomposer.reader import FutureComposerSidParser, read
from pyfuturecomposer.streams import GRAMMAR, canonical, streams


def _metadata(song: Song) -> Sequence:
    """name/author/released/load/init/play of ``song``."""
    return (song.name, song.author, song.released, song.load, song.init, song.play)


def _describe(song: Song) -> Iterable[str]:
    """Extra ``info`` lines for a Future Composer tune."""
    yield f"image bytes: {len(song.image)}"
    variant = layout.variant(song)
    for name in ("signature", "layout", "init", "play", "work"):
        yield f"{name}: {variant[name]} ({variant.source(name)})"


def _add_export_arguments(subparser) -> None:
    subparser.add_argument("song", help="Future Composer .sid/.prg file")
    subparser.add_argument("output", help="output file (.prg editor module or .sid)")
    subparser.add_argument(
        "--format",
        choices=("prg", "sid"),
        default=None,
        help="output format (default: inferred from the output extension)",
    )


def _export(args, _fmt) -> None:
    song = read(args.song, validate=False)
    fmt = args.format or ("sid" if args.output.lower().endswith(".sid") else "prg")
    (writer.write_sid if fmt == "sid" else writer.write_prg)(song, args.output)
    print(f"wrote {args.output} ({fmt})")
    if fmt == "prg" and not writer.is_editor_native(song):
        print(
            f"note: load ${song.load:04X} play ${song.play:04X} is a relocated rip; "
            "the FutureComposer editor loads the canonical $1800/$1806 build",
            file=sys.stderr,
        )


FORMAT = SidFormat(
    name="futurecomposer",
    parser=FutureComposerSidParser(),
    player=FutureComposerPlayer,
    describe=_describe,
    metadata=_metadata,
    variant=layout.variant,
    facet_sites=lambda song: layout.sites(layout.variant(song)),
    grammar=GRAMMAR,
    streams=streams,
    canonical=canonical,
    spec=spec_binding,
    probes={
        "prg": writer.to_prg,
        "sid": writer.to_sid,
        "variant": lambda song: layout.variant(song).as_info(),
    },
    commands=(
        FormatCommand(
            "export",
            "write a form the FutureComposer editor can load (.prg or .sid)",
            _add_export_arguments,
            _export,
        ),
    ),
)
