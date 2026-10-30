"""Constants for the Future Composer (MoN / Deenen) player and song format.

Addresses are those of the reference build (*We R Da Best (tune 2)*, load
``$1800``); :mod:`pyfuturecomposer.layout` locates them per build.
"""

# SID register base and PAL frame timing from the shared register map.
from pysidtracker import registers as _registers

SID_BASE = _registers.SID_BASE
# Pulse-width high registers carry only their low nibble (12-bit pulse).
PW_HI_REGS = _registers.PW_HI_REGS
PAL_CYCLES_PER_FRAME = _registers.PAL_CYCLES_PER_FRAME

# Standard Future Composer entry points (the PSID header normally matches).
DEFAULT_INIT_OFFSET = 0  # init = load
DEFAULT_PLAY_OFFSET = 6  # play = load + 6

# Reference-build table and operand offsets from the load address: the defaults
# for any facet :mod:`pyfuturecomposer.layout` does not detect.
OFF_SIGNATURE = 0x1AF  # $19af row/duration-advance code the recogniser anchors on
OFF_FREQ_LO = 0x5AB  # $1dab note freq-lo table (also the slide-target base)
OFF_FREQ_HI = 0x60B  # $1e0b note freq-hi table
OFF_SEQ_LO = 0x6EC  # $1eec per-voice sequence pointer table, low bytes
OFF_SEQ_HI = 0x6EF  # $1eef per-voice sequence pointer table, high bytes
OFF_PAT_PTR = 0x6F8  # $1ef8 interleaved pattern pointer table (id*2)
OFF_INSTR = 0x721  # $1f21 instrument record array (8-byte records)
OFF_VOICE_BASE = 0x6E9  # $1ee9 per-voice SID register base (0, 7, 14)
OFF_SPEED = 0x6E8  # $1ee8 song speed (tempo divider reload)
OFF_PW_STEP = 0x6DC  # $1edc pulse-width sweep step table
OFF_FILTER = 0x6D0  # $1ed0 filter-cutoff walk table
OFF_WAVE_ARP = 0x679  # $1e79 ($02ac & 0x40) wave/arp ctrl table
OFF_ARP_DELAY = 0x6CD  # $1ecd arp-delay table
OFF_WAVE_PROG_PTR = 0x685  # $1e85 wave-program pointer table
OFF_MOD = 0x726  # $1f26 per-instrument modulation-control bytes
OFF_SLIDE = 0x2DB  # $1adb self-modified slide-delay CMP immediate
OFF_PW_CARRY = 0x3B7  # $1bb7 pulse-width-lo carry immediate
OFF_FILT_LO = 0x6CE  # $1ece filter cutoff-lo store
OFF_FILT_HI = 0x6CF  # $1ecf filter cutoff-hi store
OFF_WAVE_CTRL = 0x492  # $1c92 self-modified wave-program control-table operand
OFF_WAVE_PITCH = 0x49A  # $1c9a self-modified wave-program pitch-table operand

# The reference build's per-voice work area ($0278..$02DA, cleared by SUB_1d65)
# and its play-state byte; other builds keep the same layout at another base.
WORK_BASE = 0x0278
WORK_SIZE = 0x63
WORK_COUNTDOWN = 0x02CA
WORK_STATE = 0x02CB

# Instrument record (8 bytes) field offsets.
INSTR_WAVEFORM = 1
INSTR_AD = 2
INSTR_SR = 3
INSTR_VIB_CTRL = 5
INSTR_PW_CTRL = 6
INSTR_MASTER_CTRL = 7

# Pattern / sequence opcode grammar boundaries.
DUR_MIN = 0x80  # 0x80..0xBF: set note duration (dur = value & 0x3F)
INSTR_MIN = 0xC0  # 0xC0..0xDF: instrument select (id = value & 0x1F)
PORTA_MIN = 0xE0  # 0xE0..0xEF: portamento/slide command (+1 arg byte)
ROWMARK_MIN = 0xF0  # 0xF0..0xFF: row, no new instrument; next byte is the note
PATTERN_END = 0xFF  # pattern terminator (after a note)
SEQ_END = 0xFE  # sequence end-of-song
SEQ_LOOP = 0xFF  # sequence loop-this-voice
SEQ_TRANSPOSE = 0x80  # bit7 set in a sequence byte = transpose (& 0x1F)
SEQ_REPEAT = 0x40  # bit6 set = repeat-count (& 0x3F)

# DAT_02c9 filter-routing accumulator base, seeded by SUB_1d65 at init.
FILTER_ROUTE_SEED = 0xB0
