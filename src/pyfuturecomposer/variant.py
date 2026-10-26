"""Locate the Future Composer build and its tables from the player code.

A tune's inline tables sit at fixed offsets from the recognised player code, so
the code signature places them: where the signature lies relative to the
transcribed reference build (``constants.OFF_SIGNATURE``) is the shift applied to
every table.  Each fact about the build -- which signature alternative matched,
that shift, every table offset, the init/play entry offsets -- is a
:class:`pysidtracker.Facet`, so a :class:`pysidtracker.Variant` reports it with
its provenance (``detected@$addr``, ``inferred(...)`` or ``default``).  Table
and entry values are offsets from the load address (relocation-safe).
"""

from typing import Dict, Optional, Tuple

from pysidtracker import (
    CodePattern,
    Facet,
    FacetRegistry,
    SidImage,
    SitePattern,
    Variant,
    find_code_first,
)
from pysidtracker.facets import Finding, detected, inferred
from pysidtracker.image import MEM_SIZE

from pyfuturecomposer import constants
from pyfuturecomposer.model import Song

# Relocation-independent MoN/FutureComposer player signatures.  Every operand
# that carries an absolute address (relocation-dependent) or a per-tune zero-page
# pointer is a wildcard (``??``); only the opcodes and fixed immediates remain.
# Both were verified byte-for-byte against the MoN/FutureComposer HVSC corpus:
# the first (a fragment of the per-voice row/duration advance -- INC ,X / LDY ,X /
# LDA (zp),Y / CMP #$FF ...) matches the vast majority; the second (the STA $D417
# filter store followed by LDY #6 / six DEY / LDA (zp),Y) covers the handful of
# player revisions the first misses.  Together they cover the corpus.
SIG_ROW_ADVANCE = (
    "FE ?? ?? BC ?? ?? B1 ?? C9 FF D0 ?? A9 00 9D ?? ?? "
    "BD ?? ?? F0 05 DE ?? ?? 10 03"
)
SIG_FILTER_STORE = "8D 17 D4 A0 06 88 88 88 88 88 88 B1 ??"

# One site reporting which alternative matched ("row_advance" / "filter_store").
SITE = SitePattern(
    f"( row_advance: {SIG_ROW_ADVANCE} | filter_store: {SIG_FILTER_STORE} )",
    first=True,
)
_ROW_ADVANCE = CodePattern(SIG_ROW_ADVANCE)

BUILDS = ("row_advance", "filter_store")

# Inline table / patch-site name -> its offset from load in the reference build.
TABLE_OFFSETS: Dict[str, int] = {
    "freq_lo": constants.OFF_FREQ_LO,
    "freq_hi": constants.OFF_FREQ_HI,
    "seq_lo": constants.OFF_SEQ_LO,
    "seq_hi": constants.OFF_SEQ_HI,
    "pat_ptr": constants.OFF_PAT_PTR,
    "instr": constants.OFF_INSTR,
    "voice_base": constants.OFF_VOICE_BASE,
    "speed": constants.OFF_SPEED,
    "pw_step": constants.OFF_PW_STEP,
    "filter": constants.OFF_FILTER,
    "wave_arp": constants.OFF_WAVE_ARP,
    "arp_delay": constants.OFF_ARP_DELAY,
    "wave_prog_ptr": constants.OFF_WAVE_PROG_PTR,
    "wave_prog_pitch": constants.OFF_WAVE_PROG_PITCH,
    "wave_prog_ctrl": constants.OFF_WAVE_PROG_CTRL,
    "mod": constants.OFF_MOD,
    "slide_lo": constants.OFF_SLIDE_LO,
    "pw_carry": constants.OFF_PW_CARRY,
    "filt_lo": constants.OFF_FILT_LO,
    "filt_hi": constants.OFF_FILT_HI,
    "wave_prog_self": constants.OFF_WAVE_PROG_SELF,
}


def _build(image: SidImage) -> Optional[Finding]:
    site = SITE.find_first(image)
    if site is None:
        return None
    return Finding(site.alt, detected(site.addr))


def _shift(image: SidImage) -> Optional[Tuple[int, int]]:
    """(table shift, signature address) from the row-advance signature, or None.

    A shift that would put a table before the load address is not a layout.
    """
    match = find_code_first(image, _ROW_ADVANCE, start=image.load, end=image.end)
    if match is None:
        return None
    shift = match.addr - image.load - constants.OFF_SIGNATURE
    if min(TABLE_OFFSETS.values()) + shift < 0:
        return None
    return shift, match.addr


def _layout(image: SidImage) -> Optional[Finding]:
    found = _shift(image)
    return None if found is None else Finding(found[0], detected(found[1]))


def _table(name: str):
    base = TABLE_OFFSETS[name]

    def detect(image: SidImage) -> Optional[Finding]:
        found = _shift(image)
        if found is None:
            return None
        return Finding(base + found[0], detected(found[1]))

    return detect


def _entry(attr: str):
    def detect(image: SidImage) -> Optional[Finding]:
        header = image.header
        addr = getattr(header, attr, 0) if header is not None else 0
        if not addr:
            return None
        return Finding(addr - image.load, inferred("psid header"))

    return detect


REGISTRY = FacetRegistry(
    [
        Facet("build", "build", BUILDS, BUILDS[0], _build),
        Facet("layout", "layout", None, 0, _layout),
        *(
            Facet(name, "layout", None, off, _table(name))
            for name, off in TABLE_OFFSETS.items()
        ),
        Facet(
            "init", "init", None, constants.DEFAULT_INIT_OFFSET, _entry("init_address")
        ),
        Facet(
            "play", "init", None, constants.DEFAULT_PLAY_OFFSET, _entry("play_address")
        ),
    ]
)


def song_image(song: Song) -> SidImage:
    """A :class:`~pysidtracker.SidImage` of ``song``'s image at its load address."""
    mem = bytearray(MEM_SIZE)
    body = song.image[: MEM_SIZE - song.load]
    mem[song.load : song.load + len(body)] = body
    return SidImage(mem, song.load, song.load + len(body), None, bytes(body), b"")


def detect(image: SidImage) -> Variant:
    """The :class:`~pysidtracker.Variant` of a loaded ``image``."""
    return REGISTRY.detect(image)


def variant_of(song: Song) -> Variant:
    """The :class:`~pysidtracker.Variant` of ``song`` (entry points from its header)."""
    variant = detect(song_image(song))
    for name, addr, default in (
        ("init", song.init, constants.DEFAULT_INIT_OFFSET),
        ("play", song.play, constants.DEFAULT_PLAY_OFFSET),
    ):
        if addr - song.load != default:
            variant = variant.replace(name, addr - song.load, inferred("song header"))
    return variant
