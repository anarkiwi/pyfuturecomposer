"""Locate a Future Composer build's tables, work area and entry from its player code.

Each address is the operand of the code that uses it: :data:`PLAY_CHAIN` walks the
play entry, :data:`SITES` capture table loads and self-modifying stores.  Every
facet is ``detected@$addr`` or the reference build's ``default``.
"""

from typing import Dict, Optional

from pysidtracker import (
    ChainError,
    CodePattern,
    Facet,
    FacetRegistry,
    Finding,
    RoutineChain,
    SidImage,
    SitePattern,
    Variant,
    SidError,
    find_code_first,
    follow_jmp,
    image_after_init,
)
from pysidtracker.facets import DETECTED, detected, inferred

from pyfuturecomposer import constants, writer
from pyfuturecomposer.model import Song

# Reference-build offset of each recogniser alternative from the load address.
SIGNATURE_OFFSETS = {"row": constants.OFF_SIGNATURE, "filter": 0x42E}

SIGNATURE = SitePattern(
    "( row: FE ?? ?? BC ?? ?? B1 ?? C9 FF D0 ?? A9 00 9D ?? ?? "
    "BD ?? ?? F0 05 DE ?? ?? 10 03 "
    "| filter: 8D 17 D4 A0 06 88 88 88 88 88 88 B1 ?? )",
    first=True,
)

PLAY_CHAIN = RoutineChain(
    (
        ("entry", "AD {state:w} C9 02 F0 ?? C9 01 D0 {to_tick} 4C ?? ?? 60"),
        (
            "to_tick",
            "EE ?? ?? EE ?? ?? EE ?? ?? A9 1F 8D 18 D4 A2 02 CE ?? ?? 10 ?? "
            "AD {tempo:w} 8D ?? ??",
        ),
    )
)

TICK_CHAIN = RoutineChain(
    (
        (
            "entry",
            "EE ?? ?? EE ?? ?? EE ?? ?? A9 1F 8D 18 D4 A2 02 CE {ca:w} 10 ?? "
            "AD {tempo:w} 8D ?? ??",
        ),
    )
)

SITES = tuple(
    CodePattern(spec)
    for spec in (
        "86 ?? BD {voice_base:w} 8D ?? ?? A8 AD ?? ?? CD ?? ?? D0",
        "BD {seq_lo:w} 85 ?? BD {seq_hi:w} 85 ?? DE ?? ?? 30",
        "0A A8 B9 {pat_ptr:w} 85 ?? B9 ?? ?? 85 ?? A9 00 9D",
        "A8 B9 {freq_lo:w} 48 B9 {freq_hi:w} AC ?? ?? 99 01 D4",
        "BD {instr:w} 48 BD ?? ?? A6 ?? 9D",
        "0A 0A 0A A8 B9 {mod:w} 8D ?? ?? B9 ?? ?? 8D",
        "68 29 0F 8D {slide:w} FE",
        "0A 0A A8 B9 {pw_step:w} DD ?? ?? 90",
        "A9 00 8D {pw_carry:w} BD ?? ?? 29 80",
        "29 03 AA BD {wave_arp:w} A6 ?? 9D",
        "A9 {filter_lo} 85 ?? A9 {filter_hi} 85 ?? A6 ?? BD ?? ?? A0 0B",
        "29 0F AA BD {wave_prog_ptr:w} 8D {wave_ctrl:w} BD ?? ?? 8D ?? ?? "
        "BD ?? ?? 8D {wave_pitch:w}",
        "AA BD {arp_delay:w} 85 ?? A6 ?? BD",
        "8D {filt_hi:w} 8E {filt_lo:w} 4C",
    )
)

# Reference-build value of each located facet: load-relative, ``work`` absolute.
DEFAULTS = {
    "play": constants.DEFAULT_PLAY_OFFSET,
    "work": constants.WORK_BASE,
    "tempo": constants.OFF_SPEED,
    "voice_base": constants.OFF_VOICE_BASE,
    "seq_lo": constants.OFF_SEQ_LO,
    "seq_hi": constants.OFF_SEQ_HI,
    "pat_ptr": constants.OFF_PAT_PTR,
    "freq_lo": constants.OFF_FREQ_LO,
    "freq_hi": constants.OFF_FREQ_HI,
    "instr": constants.OFF_INSTR,
    "mod": constants.OFF_MOD,
    "slide": constants.OFF_SLIDE,
    "pw_step": constants.OFF_PW_STEP,
    "pw_carry": constants.OFF_PW_CARRY,
    "wave_arp": constants.OFF_WAVE_ARP,
    "filter": constants.OFF_FILTER,
    "wave_prog_ptr": constants.OFF_WAVE_PROG_PTR,
    "wave_ctrl": constants.OFF_WAVE_CTRL,
    "wave_pitch": constants.OFF_WAVE_PITCH,
    "arp_delay": constants.OFF_ARP_DELAY,
    "filt_hi": constants.OFF_FILT_HI,
    "filt_lo": constants.OFF_FILT_LO,
}


def _found(name: str):
    return lambda found: found.get(name)


FACETS = FacetRegistry(
    [
        Facet("signature", "build", tuple(SIGNATURE_OFFSETS), detector=_found("sig")),
        Facet("layout", "build", detector=_found("layout")),
        Facet(
            "init",
            "init",
            default=constants.DEFAULT_INIT_OFFSET,
            detector=_found("init"),
        ),
        Facet("state", "layout", default=1, detector=_found("state")),
        *(
            Facet(
                name,
                "init" if name == "play" else "layout",
                default=value,
                detector=_found(name),
            )
            for name, value in DEFAULTS.items()
        ),
    ]
)


def _signature(image, load: int, found: Dict[str, Finding]) -> None:
    hit = SIGNATURE.find_first(image)
    if hit is not None:
        found["sig"] = Finding(hit.alt, detected(hit.addr))
        layout = hit.addr - load - SIGNATURE_OFFSETS[hit.alt]
        found["layout"] = Finding(layout, detected(hit.addr))


def _chain(image, load: int, play: int, found: Dict[str, Finding]) -> bool:
    """Record the play entry reached from ``play``, through any ``JMP`` trampolines
    or at the standard offset; True when a play chain matched.  A build without
    the state-byte test at its entry matches :data:`TICK_CHAIN` and has no state."""
    entries = tuple(
        dict.fromkeys(
            (play, follow_jmp(image, play), load + constants.DEFAULT_PLAY_OFFSET)
        )
    )
    for entry in entries:
        try:
            chain = PLAY_CHAIN.discover(image, entry)
        except ChainError:
            continue
        work = chain["state"] - (constants.WORK_STATE - constants.WORK_BASE)
        found["play"] = Finding(entry - load, detected(entry))
        found["work"] = Finding(work, detected(entry))
        found["tempo"] = Finding(chain["tempo"] - load, detected(chain["to_tick"]))
        return True
    for entry in entries:
        try:
            chain = TICK_CHAIN.discover(image, entry)
        except ChainError:
            continue
        work = chain["ca"] - (constants.WORK_COUNTDOWN - constants.WORK_BASE)
        found["play"] = Finding(entry - load, detected(entry))
        found["work"] = Finding(work, detected(entry))
        found["tempo"] = Finding(chain["tempo"] - load, detected(entry))
        found["state"] = Finding(0, detected(entry))
        return True
    return False


def _after_init(image):
    """``image`` after its own init, or None when the init cannot run."""
    try:
        return image_after_init(image)
    except SidError:
        return None


def _sites(image, load: int, found: Dict[str, Finding]) -> None:
    for pattern in SITES:
        hit = find_code_first(image, pattern)
        if hit is None:
            continue
        caps = dict(hit.captures)
        if "filter_lo" in caps:
            caps = {"filter": caps["filter_lo"] | caps["filter_hi"] << 8}
        for name, value in caps.items():
            offset = (value - load) & 0xFFFF
            found.setdefault(name, Finding(offset, detected(hit.addr)))


def detect(image, init: Optional[int] = None, play: Optional[int] = None) -> Variant:
    """The :class:`~pysidtracker.Variant` of the FC build in ``image``.

    ``image`` is a :class:`~pysidtracker.SidImage` whose loaded span is scanned;
    ``init`` / ``play`` default to its header entry points (else load / load + 6).
    """
    load = image.load
    header = image.header
    if play is None:
        play = (header and header.play_address) or load + constants.DEFAULT_PLAY_OFFSET
    if init is None:
        init = (header and header.init_address) or load
    found: Dict[str, Finding] = {"init": Finding(init - load, inferred("header"))}
    _signature(image, load, found)
    scanned = image
    if not _chain(image, load, play, found):
        booted = _after_init(image)
        if booted is not None and _chain(booted, load, play, found):
            scanned = booted
    _sites(scanned, load, found)
    return FACETS.detect(found)


def song_image(song: Song) -> SidImage:
    """``song`` loaded as a :class:`~pysidtracker.SidImage` with its entry points."""
    return SidImage.from_bytes(writer.to_sid(song))


def variant(song: Song) -> Variant:
    """The :func:`detect` variant of ``song``."""
    return detect(song_image(song))


def sites(found: Variant) -> Dict[int, str]:
    """``{addr: facet}`` of every facet detected at a code address."""
    out: Dict[int, str] = {}
    for name in found:
        src = found.source(name)
        if src.kind == DETECTED and src.addr is not None:
            out.setdefault(src.addr, name)
    return out
