"""Variant detection (:mod:`pyfuturecomposer.layout`) over crafted and real builds."""

import pytest

from pysidtracker import SidImage
from pysidtracker.header import write_psid

from pyfuturecomposer import layout, read
from pyfuturecomposer.formats import FORMAT

LOAD = 0x1000
SIZE = 0x800

ROW = bytes.fromhex("FE0000BC0000B100C9FFD000A9009D0000BD0000F005DE00001003")
FILTER = bytes.fromhex("8D17D4A006888888888888B100")

PLAY_OFF = 0x20
TICK_OFF = 0x40
STATE = 0x0400
SPEED_OFF = 0x123
ENTRY = bytes.fromhex(f"AD{STATE & 0xFF:02X}{STATE >> 8:02X}C902F000C901D0")
ENTRY += bytes([TICK_OFF - PLAY_OFF - 11]) + bytes.fromhex("4C000060")
TICK = bytes.fromhex("EE0000EE0000EE0000A91F8D18D4A202CE00001000AD")
TICK += (LOAD + SPEED_OFF).to_bytes(2, "little") + bytes.fromhex("8D0000")


def _image(patches, play=LOAD + 6):
    img = bytearray(SIZE)
    for off, chunk in patches.items():
        img[off : off + len(chunk)] = chunk
    data = write_psid(load=LOAD, init=LOAD, play=play, image=bytes(img))
    return SidImage.from_bytes(data)


def _word(addr):
    return addr.to_bytes(2, "little")


def _defaulted(variant, names):
    return {n: (variant[n], str(variant.source(n))) for n in names}


@pytest.mark.parametrize(
    "alt,code", [("row", ROW), ("filter", FILTER)], ids=("row", "filter")
)
@pytest.mark.parametrize("k", [0, 0x40, -0x100])
def test_signature_alternative_gives_layout(alt, code, k):
    addr = layout.SIGNATURE_OFFSETS[alt] + k
    v = layout.detect(_image({addr: code}))
    assert (v["signature"], v["layout"]) == (alt, k)
    assert str(v.source("signature")) == f"detected@${LOAD + addr:04x}"


def test_no_signature_is_none():
    assert layout.detect(_image({}))["signature"] is None


def test_play_chain_detects_play_work_tempo():
    v = layout.detect(_image({PLAY_OFF: ENTRY, TICK_OFF: TICK}, play=LOAD + PLAY_OFF))
    assert v["play"] == PLAY_OFF
    assert v["work"] == STATE - 0x53
    assert v["tempo"] == SPEED_OFF
    assert str(v.source("play")) == f"detected@${LOAD + PLAY_OFF:04x}"
    assert str(v.source("tempo")) == f"detected@${LOAD + TICK_OFF:04x}"


@pytest.mark.parametrize(
    "patches",
    [
        {PLAY_OFF: ENTRY, TICK_OFF: TICK.replace(b"\xa9\x1f", b"\xa9\x1e")},
        {PLAY_OFF: ENTRY.replace(b"\xc9\x02", b"\xc9\x03"), TICK_OFF: TICK},
        {PLAY_OFF + 1: ENTRY, TICK_OFF: TICK},
    ],
)
def test_play_chain_mismatch_defaults(patches):
    v = layout.detect(_image(patches, play=LOAD + PLAY_OFF))
    names = ("play", "work", "tempo")
    assert _defaulted(v, names) == {n: (layout.DEFAULTS[n], "default") for n in names}


def _sites_image():
    freq = bytes.fromhex("A8B9") + _word(LOAD + 0x300) + b"\x48\xb9"
    freq += _word(LOAD + 0x360) + bytes.fromhex("AC00009901D4")
    filt = bytes.fromhex("A9348500A9128500A600BD0000A00B")
    wave = bytes.fromhex("290FAABD") + _word(LOAD + 0x400) + b"\x8d"
    wave += _word(LOAD + 0x410) + bytes.fromhex("BD00008D0000BD00008D")
    wave += _word(LOAD + 0x420)
    return _image({0x100: freq, 0x140: filt, 0x180: wave})


def test_sites_capture_tables():
    v = layout.detect(_sites_image())
    got = {n: (v[n], str(v.source(n))) for n in layout.DEFAULTS}
    expect = {n: (value, "default") for n, value in layout.DEFAULTS.items()}
    expect.update(
        freq_lo=(0x300, "detected@$1100"),
        freq_hi=(0x360, "detected@$1100"),
        filter=(0x1234 - LOAD, "detected@$1140"),
        wave_prog_ptr=(0x400, "detected@$1180"),
        wave_ctrl=(0x410, "detected@$1180"),
        wave_pitch=(0x420, "detected@$1180"),
    )
    assert got == expect


def test_sites_maps_detected_addresses():
    assert layout.sites(layout.detect(_sites_image())) == {
        0x1100: "freq_lo",
        0x1140: "filter",
        0x1180: "wave_prog_ptr",
    }


def test_reference_build_is_the_defaults(tune_path):
    v = layout.variant(read(tune_path))
    assert (v["signature"], v["layout"], v["init"]) == ("row", 0, 0)
    assert {n: v[n] for n in layout.DEFAULTS} == layout.DEFAULTS
    assert all(v.source(n).kind == "detected" for n in layout.DEFAULTS)


def test_format_variant_hooks(tune_path):
    song = read(tune_path)
    info = FORMAT.variant_info(song)
    assert info["signature"] == "row"
    assert info["signature.src"] == "detected@$19af"
    assert FORMAT.sites(song) == layout.sites(layout.variant(song))
    assert set(FORMAT.sites(song).values()) >= {"play", "freq_lo", "filter"}
