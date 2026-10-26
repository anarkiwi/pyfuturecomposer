"""Table placement from the recognised player signature (``variant``)."""

import pytest
from pysidtracker.header import write_psid

from pyfuturecomposer import constants, parse
from pyfuturecomposer.variant import SIG_FILTER_STORE, SIG_ROW_ADVANCE, variant_of


def _song(sig: str, pad: int):
    body = bytes.fromhex(sig.replace("??", "00"))
    image = b"\x00" * pad + body + b"\x00" * 0x900
    return parse(write_psid(load=0x1800, init=0x1800, play=0x1806, image=image))


def test_reference_layout_is_default_offsets():
    var = variant_of(_song(SIG_ROW_ADVANCE, constants.OFF_SIGNATURE))
    assert var["build"] == "row_advance"
    assert var["layout"] == 0
    assert var["freq_lo"] == constants.OFF_FREQ_LO
    assert str(var.source("layout")) == "detected@$19af"


def test_shifted_signature_shifts_tables():
    var = variant_of(_song(SIG_ROW_ADVANCE, constants.OFF_SIGNATURE + 0x10))
    assert var["layout"] == 0x10
    assert var["freq_lo"] == constants.OFF_FREQ_LO + 0x10
    assert var["instr"] == constants.OFF_INSTR + 0x10


def test_filter_store_build_keeps_default_layout():
    var = variant_of(_song(SIG_FILTER_STORE, 0x40))
    assert var["build"] == "filter_store"
    assert var["layout"] == 0
    assert str(var.source("layout")) == "default"


@pytest.mark.parametrize("name", ["init", "play"])
def test_entry_offsets_follow_song_header(name):
    song = parse(write_psid(load=0x1800, init=0x1810, play=0x1820, image=b"\x00" * 8))
    var = variant_of(song)
    assert var[name] == {"init": 0x10, "play": 0x20}[name]
