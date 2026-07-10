"""Constants for the Future Composer (MoN / Deenen) player and song format.

Values follow the decompiled Future Composer player (``entry_1806`` of the
MoN/FutureComposer player, reverse-engineered from the representative tune
*We R Da Best (tune 2)* by Warren Pilbrough / Jade Tiger), cross-checked
byte-exact against the ``preframr-sidtrace`` register oracle.  The player code is
identical across tunes of this variant; only its DATA (sequences, patterns,
instruments, mod tables) differs, carried inline at fixed offsets-from-load.

FC is RELOCATABLE (init = load, play = load + 6); every absolute address in the
disassembly is load-relative, so the constants here are OFFSETS-FROM-LOAD and the
player reads/writes them at ``load + offset``.
"""

# SID register map and C64 frame timing are documented hardware facts owned by
# the shared pysidtracker hardware-register surface; re-export them here for
# back-compat (``SID_REGISTERS`` is the shared ``SID_REG_COUNT``).
from pysidtracker import registers as _registers

SID_BASE = _registers.SID_BASE
SID_REG_COUNT = _registers.SID_REG_COUNT
SID_VOICE_OFFSET = _registers.SID_VOICE_OFFSET
# Pulse-width high registers carry only their low nibble (12-bit pulse).
PW_HI_REGS = _registers.PW_HI_REGS
PAL_CLOCK_HZ = _registers.PAL_CLOCK_HZ
PAL_CYCLES_PER_FRAME = _registers.PAL_CYCLES_PER_FRAME
NTSC_CLOCK_HZ = _registers.NTSC_CLOCK_HZ
NTSC_CYCLES_PER_FRAME = _registers.NTSC_CYCLES_PER_FRAME

MODE_VOL_REG = 0x18
RES_FILT_REG = 0x17
FC_HI_REG = 0x16

# Cycles between consecutive register writes within one frame (approximates the
# store instructions of the 6502 playroutine).
DEFAULT_WRITE_SPACING = 16

# Standard Future Composer entry points (the PSID header normally matches).
DEFAULT_INIT_OFFSET = 0  # init = load
DEFAULT_PLAY_OFFSET = 6  # play = load + 6

# ---------------------------------------------------------------------------
# Player-code / inline-table OFFSETS-FROM-LOAD.  The player binary is identical
# across tunes of this variant, so each table lives at a fixed offset from the
# load address (relocation-safe -- the same offsets work for any load address).
# Derived directly from the disassembly (subtract $1800 from the absolute addr).
# ---------------------------------------------------------------------------
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
OFF_WAVE_PROG_PITCH = 0x68D  # $1e8d wave-program pitch table
OFF_WAVE_PROG_CTRL = 0x69D  # $1e9d wave-program control table
OFF_MOD = 0x726  # $1f26 per-instrument modulation-control bytes
OFF_SLIDE_LO = 0x2DB  # $1adb self-modified slide-lo store
OFF_PW_CARRY = 0x3B7  # $1bb7 pulse-width-lo carry immediate
OFF_FILT_LO = 0x6CE  # $1ece filter cutoff-lo store
OFF_FILT_HI = 0x6CF  # $1ecf filter cutoff-hi store
OFF_WAVE_PROG_SELF = 0x492  # $1c92 self-modified wave-program pointer slots

# Instrument record (8 bytes) field offsets.
INSTR_RECORD_SIZE = 8
INSTR_PULSE_CTRL = 0
INSTR_WAVEFORM = 1
INSTR_AD = 2
INSTR_SR = 3
INSTR_AUX = 4
INSTR_VIB_CTRL = 5
INSTR_PW_CTRL = 6
INSTR_MASTER_CTRL = 7

# Pattern / sequence opcode grammar boundaries.
NOTE_MAX = 0x7F  # < 0x80: a note (indexes the freq tables)
DUR_MIN = 0x80  # 0x80..0xBF: set note duration (dur = value & 0x3F)
INSTR_MIN = 0xC0  # 0xC0..0xDF: instrument select (id = value & 0x1F)
PORTA_MIN = 0xE0  # 0xE0..0xEF: portamento/slide command (+1 arg byte)
ROWMARK_MIN = 0xF0  # 0xF0..0xFF: row, no new instrument; next byte is the note
PATTERN_END = 0xFF  # pattern terminator (after a note)
SEQ_END = 0xFE  # sequence end-of-song
SEQ_LOOP = 0xFF  # sequence loop-this-voice
SEQ_TRANSPOSE = 0x80  # bit7 set in a sequence byte = transpose (& 0x1F)
SEQ_REPEAT = 0x40  # bit6 set = repeat-count (& 0x3F)
INSTR_MASK = 0x1F
DUR_MASK = 0x3F

# DAT_02c9 filter-routing accumulator base, seeded by SUB_1d65 at init.
FILTER_ROUTE_SEED = 0xB0
