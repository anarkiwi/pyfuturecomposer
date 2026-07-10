"""The Future Composer per-frame play routine, as a faithful 6502 transcription.

A pure-Python reimplementation of FC's ``entry_1806`` play routine
(reverse-engineered from the MoN/FutureComposer player), reproducing the per-frame
SID register writes byte-exact.  The cleanest faithful transcription models a flat
64 KiB 6502 memory (so the player's indirect ``(zp),Y`` addressing and its
self-modifying immediates land EXACTLY where the chip puts them) seeded with the
tune image at its load address; the work RAM the player clears at init starts at
zero.

The routine: a global tempo divider, a per-voice DEC-duration row advance, two
opcode-stream walks (the per-voice SEQUENCE / orderlist + the per-voice PATTERN),
and the dense per-frame instrument modulation engine -- slide-target vibrato /
portamento, the ``$E0`` glide, a 16-bit pulse-width sweep, the filter-cutoff
program and the wave / arp tables.  Every threshold / mask / range is an FC player
constant transcribed from the disassembly (:mod:`pyfuturecomposer.constants`).
"""

# A faithful 6502 transcription: the single per-frame routine inherently carries
# the player's branch density and its full per-voice work-byte set.
# pylint: disable=too-many-instance-attributes,too-many-statements
# pylint: disable=too-many-branches,too-many-locals,too-many-return-statements

from typing import Iterator, List, Tuple

from pyfuturecomposer import constants
from pyfuturecomposer.model import Song

SID_REG_BASE = constants.SID_BASE
NREG = constants.SID_REG_COUNT


def _s8(value: int) -> int:
    """Interpret ``value`` (a byte) as a signed 8-bit int (the 6502 sign test)."""
    value &= 0xFF
    return value - 0x100 if value & 0x80 else value


class _Mem:
    """A flat 64 KiB 6502 memory model seeded with the tune image."""

    def __init__(self, image: bytes, load: int):
        self.mem = bytearray(0x10000)
        self.mem[load : load + len(image)] = image
        self._writes: List[Tuple[int, int]] = []

    def r(self, addr: int) -> int:
        """Read a byte at ``addr`` (16-bit wrap)."""
        return self.mem[addr & 0xFFFF]

    def w(self, addr: int, val: int) -> None:
        """Write a byte; SID register writes are also captured for the reglog."""
        addr &= 0xFFFF
        val &= 0xFF
        self.mem[addr] = val
        reg = addr - SID_REG_BASE
        if 0 <= reg < NREG:
            self._writes.append((reg, val))

    def take(self) -> List[Tuple[int, int]]:
        """Return + clear this frame's captured SID ``(reg, val)`` writes."""
        out = self._writes
        self._writes = []
        return out


class Player:
    """The Future Composer per-frame player over a parsed :class:`Song`."""

    def __init__(self, song: Song):
        load = song.load
        c = constants
        self.load = load
        self.freq_lo = load + c.OFF_FREQ_LO
        self.freq_hi = load + c.OFF_FREQ_HI
        self.seq_lo = load + c.OFF_SEQ_LO
        self.seq_hi = load + c.OFF_SEQ_HI
        self.pat_ptr = load + c.OFF_PAT_PTR
        self.instr = load + c.OFF_INSTR
        self.voice_base = load + c.OFF_VOICE_BASE
        self.speed_addr = load + c.OFF_SPEED
        self.t_pwstep = load + c.OFF_PW_STEP
        self.t_filter = load + c.OFF_FILTER
        self.t_wavearp = load + c.OFF_WAVE_ARP
        self.t_arpdelay = load + c.OFF_ARP_DELAY
        self.t_waveptr = load + c.OFF_WAVE_PROG_PTR
        self.t_wavepitch = load + c.OFF_WAVE_PROG_PITCH
        self.t_wavectrl = load + c.OFF_WAVE_PROG_CTRL
        self.mod = load + c.OFF_MOD
        self.a_slide_lo = load + c.OFF_SLIDE_LO
        self.a_pw_carry = load + c.OFF_PW_CARRY
        self.a_filt_lo = load + c.OFF_FILT_LO
        self.a_filt_hi = load + c.OFF_FILT_HI
        self.a_wave_self = load + c.OFF_WAVE_PROG_SELF
        self.mem = _Mem(song.image, load)
        self.finished = False
        self._init_state()

    # ---- 6502 arithmetic primitives -------------------------------------
    @staticmethod
    def _adc(a: int, m: int, carry_in: int) -> Tuple[int, int]:
        """6502 ADC: ``A + M + C`` -> ``(result_byte, carry_out)`` (binary mode)."""
        total = (a & 0xFF) + (m & 0xFF) + (carry_in & 1)
        return total & 0xFF, 1 if total > 0xFF else 0

    @staticmethod
    def _sbc(a: int, m: int, carry_in: int) -> Tuple[int, int]:
        """6502 SBC: ``A - M - (1-C)`` -> ``(result_byte, carry_out)``."""
        total = (a & 0xFF) - (m & 0xFF) - (1 - (carry_in & 1))
        return total & 0xFF, 1 if total >= 0 else 0

    def r(self, addr: int) -> int:
        """Memory read."""
        return self.mem.r(addr)

    def w(self, addr: int, val: int) -> None:
        """Memory write (captures SID writes)."""
        self.mem.w(addr, val)

    def vget(self, base: int, x: int) -> int:
        """Read voice ``x``'s byte from the work array based at ``base``."""
        return self.mem.r(base + x)

    def vset(self, base: int, x: int, val: int) -> None:
        """Write voice ``x``'s byte to the work array based at ``base``."""
        self.mem.w(base + x, val & 0xFF)

    # ---- init (LAB_1d74 / SUB_1d65) -------------------------------------
    def _init_state(self) -> None:
        self.w(0x0299, 0)
        self.w(0x029A, 0)
        self.w(0x029B, 0)
        for x in range(3):
            self.w(0x0278 + x, 0)
            self.w(0x027B + x, 0)
            self.w(0x027E + x, 0)
            self.w(0x0287 + x, 0)
        self.w(0x02CB, 0)
        self.w(0x02CA, 0)
        # SUB_1d65 seeds DAT_02c9 to $B0 (filter-routing accumulator base).
        self.w(0x02C9, constants.FILTER_ROUTE_SEED)

    def _silence(self) -> None:
        for off in range(0x18):
            self.w(SID_REG_BASE + off, 0)

    # ---- one frame (entry_1806) -----------------------------------------
    def play_frame(self) -> List[Tuple[int, int]]:
        """Run one ``entry_1806`` tick; return the captured ``(reg, val)`` writes."""
        state = self.r(0x02CB)
        if state == 2:  # 1814 RTS (stopped)
            return self.mem.take()
        if state == 1:  # do-init -> LAB_1d74
            self._init_state()
            return self.mem.take()
        self.w(0x0299, (self.r(0x0299) + 1) & 0xFF)
        self.w(0x029A, (self.r(0x029A) + 1) & 0xFF)
        self.w(0x029B, (self.r(0x029B) + 1) & 0xFF)
        self.w(SID_REG_BASE + 0x18, 0x1F)
        speed = self.r(self.speed_addr)
        dec = _s8(self.r(0x02CA) - 1)
        if dec < 0:
            dec = speed
        self.w(0x02CA, dec & 0xFF)
        x = 2
        while True:
            self._voice(x, speed)
            x -= 1
            if x < 0:
                break
        self.finished = self.r(0x02CB) == 2
        return self.mem.take()

    def _voice(self, x: int, speed: int) -> None:
        ad = self.r(self.voice_base + x)
        self.w(0x02AD, ad)
        self.w(0x00FF, x)
        if self.r(0x02CA) == speed:  # 183c row-advance frame
            self._row_advance(x)
        else:  # 1853 sustain
            self._sustain(x)

    def _row_advance(self, x: int) -> None:
        seq_lo = self.r(self.seq_lo + x)
        seq_hi = self.r(self.seq_hi + x)
        self.w(0x00FB, seq_lo)
        self.w(0x00FC, seq_hi)
        seq_ptr = seq_lo | (seq_hi << 8)
        c = _s8(self.vget(0x027E, x) - 1)
        self.vset(0x027E, x, c)
        if c >= 0:
            self._lab_19dd(x)
            return
        self._sequence_walk(x, seq_ptr)

    def _lab_19dd(self, x: int) -> None:
        if self.vget(0x0299, x) != 0:
            self.vset(0x02D0, x, self.vget(0x0284, x) & 0xFE)
        self._sustain(x)

    def _sequence_walk(self, x: int, seq_ptr: int) -> None:
        while True:
            cur = self.vget(0x0278, x)
            b = self.r(seq_ptr + cur)
            if b == constants.SEQ_END:  # 1874 end of song
                self._silence()
                self.w(0x02CB, 2)
                return
            if b == constants.SEQ_LOOP:  # 1863 loop this voice
                self.vset(0x027E, x, 0)
                self.vset(0x0278, x, 0)
                self.vset(0x027B, x, 0)
                self.w(0x02C9, 0)
                continue
            self.w(0x02BE, b)
            if b & constants.SEQ_TRANSPOSE:  # 187e transpose
                self.vset(0x02A6, x, b & 0x1F)
                self.vset(0x0278, x, (self.vget(0x0278, x) + 1) & 0xFF)
                continue
            if b & constants.SEQ_REPEAT:  # 1893 repeat-count
                self.vset(0x02CD, x, b & 0x3F)
                self.vset(0x0278, x, (self.vget(0x0278, x) + 1) & 0xFF)
                continue
            break
        y = (b << 1) & 0xFF
        pat_lo = self.r(self.pat_ptr + y)
        pat_hi = self.r(self.pat_ptr + ((y + 1) & 0xFF))
        self.w(0x00FD, pat_lo)
        self.w(0x00FE, pat_hi)
        pat_ptr = pat_lo | (pat_hi << 8)
        self.vset(0x0296, x, 0)
        self.vset(0x0299, x, 0)
        self.vset(0x02B8, x, 3)
        self._pattern_walk(x, pat_ptr)

    def _pattern_walk(self, x: int, pat_ptr: int) -> None:
        cur = self.vget(0x027B, x)
        while True:
            f8 = self.r(pat_ptr + cur)
            self.w(0x00F8, f8)
            if (f8 & 0xF0) == 0xF0:  # row-set end marker (next byte is the note)
                self.vset(0x02D7, x, 1)
                cur = (cur + 1) & 0xFF
                self.vset(0x027B, x, cur)
                f8 = self.r(pat_ptr + cur)
                self.w(0x00F8, f8)
                self._lab_193a(x, pat_ptr, f8)
                return
            self.vset(0x02D7, x, 0)
            if (f8 & 0xF0) == 0xE0:  # portamento / slide command
                self.vset(0x0296, x, (f8 & 1) + 1)
                self.w(0x02BC, (f8 & 0xE) >> 1)
                cur = (cur + 1) & 0xFF
                self.vset(0x027B, x, cur)
                nb = self.r(pat_ptr + cur)
                self.w(0x02BB, nb & 0xF0)
                self.w(self.a_slide_lo, nb & 0x0F)
                cur = (cur + 1) & 0xFF
                self.vset(0x027B, x, cur)
                f8 = self.r(pat_ptr + cur)
                self.w(0x00F8, f8)
            if (f8 & 0xE0) == 0xC0:  # instrument select
                self.vset(0x028A, x, f8 & 0x1F)
                cur = self._sub_19d0(x, pat_ptr, cur)
                if cur is None:
                    return
                f8 = self.r(0x00F8)
            if (f8 & 0xC0) == 0x80:  # duration
                self.vset(0x0281, x, f8 & 0x3F)
                cur = self._sub_19d0(x, pat_ptr, cur)
                if cur is None:
                    return
                f8 = self.r(0x00F8)
                continue
            self._lab_193a(x, pat_ptr, f8)
            return

    def _sub_19d0(self, x: int, pat_ptr: int, cur: int):
        cur = (cur + 1) & 0xFF
        self.vset(0x027B, x, cur)
        b = self.r(pat_ptr + cur)
        if b == 0xFF:  # 19bb end of pattern
            self._lab_19bb(x)
            return None
        self.w(0x00F8, b)
        return cur

    def _lab_193a(self, x: int, pat_ptr: int, f8: int) -> None:
        ad = self.r(0x02AD)
        self.vset(0x027E, x, self.vget(0x0281, x))
        noteidx = (f8 + _s8(self.vget(0x02A6, x))) & 0xFF
        self.vset(0x0287, x, noteidx)
        lo = self.r(self.freq_lo + noteidx)
        hi = self.r(self.freq_hi + noteidx)
        self.w(SID_REG_BASE + 1 + ad, hi)
        self.vset(0x028D, x, hi)
        self.vset(0x0290, x, hi)
        self.w(SID_REG_BASE + 0 + ad, lo)
        self.vset(0x0293, x, lo)
        if self.vget(0x02D7, x) == 0:  # fresh note -> load instrument record
            instr = self.vget(0x028A, x)
            x8 = (instr << 3) & 0xFF
            self.w(0x02A9, x8)
            rec = self.instr + x8
            self.w(SID_REG_BASE + 5 + ad, self.r(rec + 2))
            self.w(SID_REG_BASE + 6 + ad, self.r(rec + 3))
            aux = self.r(rec + 4)
            pulse_ctrl = self.r(rec + 0)
            wf = self.r(rec + 1)
            self.vset(0x0284, x, wf)
            self.vset(0x02D0, x, wf)
            self.w(SID_REG_BASE + 2 + ad, 0)
            self.vset(0x029C, x, 0)
            self.vset(0x02A2, x, pulse_ctrl)
            pw_hi = pulse_ctrl & 0x0F
            self.w(SID_REG_BASE + 3 + ad, pw_hi)
            self.vset(0x029F, x, pw_hi)
            self.vset(0x02C6, x, 1)
            self.vset(0x02C3, x, aux)
        cur = (self.vget(0x027B, x) + 1) & 0xFF
        self.vset(0x027B, x, cur)
        if self.r(pat_ptr + cur) == 0xFF:
            self._lab_19bb(x)
            return
        self._lab_1d35(x)

    def _lab_19bb(self, x: int) -> None:
        self.vset(0x027B, x, 0)
        rc = self.vget(0x02CD, x)
        advance = True
        if rc != 0:
            nrc = _s8(rc - 1)
            self.vset(0x02CD, x, nrc & 0xFF)
            if nrc >= 0:
                advance = False
        if advance:
            self.vset(0x0278, x, (self.vget(0x0278, x) + 1) & 0xFF)
        self._lab_1d35(x)

    def _lab_1d35(self, x: int) -> None:
        ad = self.r(0x02AD)
        self.w(SID_REG_BASE + 4 + ad, self.vget(0x02D0, x))

    # ---- sustain / per-frame mod engine (LAB_19ed) ---------------------
    def _sustain(self, x: int) -> None:
        x8 = (self.vget(0x028A, x) << 3) & 0xFF
        vib = self.r(self.mod + x8 + 0)
        self.w(0x02AB, self.r(self.mod + x8 + 1))
        self.w(0x02AC, self.r(self.mod + x8 + 2))
        self.w(0x02AA, vib)
        ac = self.r(0x02AC)
        if (ac & 4) == 0 and (ac & 0x10) == 0 and vib != 0:
            self._vibrato(x, vib)
        elif vib == 0:  # 1d47 default filter cutoff
            self.w(self.a_filt_hi, 0x18)
            self.w(self.a_filt_lo, 0x0C)
            self._lab_1ace(x)
            return
        else:  # 1d52 filter cutoff from vib byte
            self.w(self.a_filt_lo, vib >> 4)
            self.w(self.a_filt_hi, vib & 0x0F)
            self._lab_1ace(x)
            return
        self._lab_1ace(x)

    def _vibrato(self, x: int, vib: int) -> None:
        self.vset(0x02AF, x, (vib & 0x78) >> 3)
        self.w(0x02AE, vib & 7)
        do_step = False
        if self.vget(0x02B2, x) == 0:
            do_step = True
        else:
            nb5 = _s8(self.vget(0x02B5, x) - 1)
            self.vset(0x02B5, x, nb5 & 0xFF)
            if nb5 == 0:
                nb2 = _s8(self.vget(0x02B2, x) + 1)
                self.vset(0x02B2, x, nb2 & 0xFF)
                if nb2 >= 0:
                    do_step = True
        if do_step:
            nb5 = (self.vget(0x02B5, x) + 1) & 0xFF
            self.vset(0x02B5, x, nb5)
            if self.vget(0x02AF, x) < self.vget(0x02B5, x):
                self.vset(0x02B5, x, self.vget(0x02AF, x))
                self.vset(0x02B2, x, (self.vget(0x02B2, x) - 1) & 0xFF)
                self.vset(0x02B5, x, (self.vget(0x02B5, x) - 1) & 0xFF)
        self._slide_target(x)
        self._lab_1ace(x)

    def _slide_target(self, x: int) -> None:
        y = self.vget(0x0287, x)
        flo_y1 = self.r(self.freq_lo + ((y + 1) & 0xFF))
        flo_y = self.r(self.freq_lo + y)
        d6, c = self._sbc(flo_y1, flo_y, 1)
        self.w(0x02D6, d6)
        fhi_y1 = self.r(self.freq_hi + ((y + 1) & 0xFF))
        fhi_y = self.r(self.freq_hi + y)
        a, c2 = self._sbc(fhi_y1, fhi_y, c)
        a, _ = self._adc(a, self.vget(0x0299, x), c2)
        a = (a & 0xFF) >> 1  # 1a62 LSR A once, then the 1a63 loop
        while True:
            ae = _s8(self.r(0x02AE) - 1)
            self.w(0x02AE, ae & 0xFF)
            if ae < 0:
                break
            carry_in = a & 1
            a = a >> 1
            new_d6 = (self.r(0x02D6) >> 1) | (carry_in << 7)
            self.w(0x02D6, new_d6 & 0xFF)
        self.w(0x02D5, a & 0xFF)
        self.w(0x02D3, flo_y)
        self.w(0x02D4, fhi_y)
        cnt = self.vget(0x02AF, x) >> 1
        yy = cnt
        while True:
            yy = _s8(yy - 1)
            if yy < 0:
                break
            nd3, c = self._sbc(self.r(0x02D3), self.r(0x02D6), 1)
            self.w(0x02D3, nd3)
            nd4, _ = self._sbc(self.r(0x02D4), self.r(0x02D5), c)
            self.w(0x02D4, nd4)
        if self.vget(0x0299, x) >= 4:
            yy = self.vget(0x02B5, x)
            while True:
                yy = _s8(yy - 1)
                if yy < 0:
                    break
                nd3, c = self._adc(self.r(0x02D3), self.r(0x02D6), 0)
                self.w(0x02D3, nd3)
                nd4, _ = self._adc(self.r(0x02D4), self.r(0x02D5), c)
                self.w(0x02D4, nd4)
            ad = self.r(0x02AD)
            self.w(SID_REG_BASE + 0 + ad, self.r(0x02D3))
            self.w(SID_REG_BASE + 1 + ad, self.r(0x02D4))

    def _lab_1ace(self, x: int) -> None:
        ad = self.r(0x02AD)
        diff = (self.vget(0x0281, x) - self.vget(0x027E, x)) & 0xFF
        if diff > 2 and self.vget(0x0296, x) != 0:
            mode = self.vget(0x0296, x) & 3
            if mode == 1:  # 1b08 add
                n293, c = self._adc(self.vget(0x0293, x), self.r(0x02BB), 0)
                self.vset(0x0293, x, n293)
                self.w(SID_REG_BASE + 0 + ad, n293)
                n28d, _ = self._adc(self.vget(0x028D, x), self.r(0x02BC), c)
                self.vset(0x028D, x, n28d)
                self.w(SID_REG_BASE + 1 + ad, n28d)
            else:  # 1ae9 subtract
                n293, c = self._sbc(self.vget(0x0293, x), self.r(0x02BB), 1)
                self.vset(0x0293, x, n293)
                self.w(SID_REG_BASE + 0 + ad, n293)
                n28d, _ = self._sbc(self.vget(0x028D, x), self.r(0x02BC), c)
                self.vset(0x028D, x, n28d)
                self.w(SID_REG_BASE + 1 + ad, n28d)
        self._pw_sweep(x, ad)

    def _pw_sweep(self, x: int, ad: int) -> None:
        d2ab = self.r(0x02AB)
        if d2ab != 0:
            yy = ((d2ab & 7) - 1) & 0xFF
            yy = (yy << 2) & 0xFF
            c299 = self.vget(0x0299, x)
            t0 = self.r(self.t_pwstep + yy)
            if t0 < c299:
                yy2 = (yy + 2) & 0xFF
                t1 = self.r(self.t_pwstep + yy2)
                if t1 < c299:
                    self.w(0x02A5, d2ab & 0xFC)
                else:
                    self.w(0x02A5, self.r(self.t_pwstep + ((yy2 + 1) & 0xFF)))
            else:
                self.w(0x02A5, self.r(self.t_pwstep + ((yy + 1) & 0xFF)))
            a5 = self.r(0x02A5)
            if self.vget(0x02C6, x) == 0:  # 1b5d subtract
                n29c, c = self._sbc(self.vget(0x029C, x), a5, 1)
                self.vset(0x029C, x, n29c)
                n29f, _ = self._sbc(self.vget(0x029F, x), 0, c)
                self.vset(0x029F, x, n29f)
                if n29f < 1:
                    self.vset(0x02C6, x, 1)
            else:  # 1b7a add
                n29c, c = self._adc(self.vget(0x029C, x), a5, 0)
                self.vset(0x029C, x, n29c)
                n29f, _ = self._adc(self.vget(0x029F, x), 0, c)
                self.vset(0x029F, x, n29f)
                if n29f >= 0x0F:
                    self.vset(0x02C6, x, 0)
        self._pw_write(x, ad)

    def _pw_write(self, x: int, ad: int) -> None:
        self.w(self.a_pw_carry, 0)
        if (self.vget(0x02A2, x) & 0x80) and (self.vget(0x0299, x) & 1):
            self.w(self.a_pw_carry, 0xB0)
        carry_imm = self.r(self.a_pw_carry)
        plo, c = self._adc(self.vget(0x029C, x), carry_imm, 0)
        self.w(SID_REG_BASE + 2 + ad, plo)
        phi, _ = self._adc(self.vget(0x029F, x), 0, c)
        self.w(SID_REG_BASE + 3 + ad, phi)
        ac = self.r(0x02AC)
        if (ac & 0x40) and self.vget(0x0299, x) >= 3:
            idx = self.vget(0x0299, x) & 3
            self.vset(0x02D0, x, self.r(self.t_wavearp + idx))
        self.w(0x02BE, ad)
        self._filter_program(x, ad)

    def _filter_program(self, x: int, ad: int) -> None:
        ac = self.r(0x02AC)
        if (ac & 1) == 0:  # 1c4d
            if self.r(0x00FF) == self.r(0x02CC):
                self._filter_cutoff_write(x, 0xFF)
            self._wave_arp(x, ad)
            return
        self.w(0x02CC, self.r(0x00FF))
        c299 = self.vget(0x0299, x)
        d6_thresh = self.r(self.t_filter + 11)
        if c299 >= d6_thresh:  # 1c33
            self._filter_walk_1c33(x)
            self._wave_arp(x, ad)
            return
        yy = 0x0A
        handled = False
        while True:
            tv = self.r(self.t_filter + yy)
            if c299 >= tv:  # 1c3e
                self._filter_walk_1c3e(x, yy)
                handled = True
                break
            yy -= 1
            if yy == 6:
                break
        if not handled:
            tv = self.r(self.t_filter + 6)
            if c299 >= tv:  # 1c15
                self._filter_resonance()
                self._filter_walk_1c33(x)
            else:
                self._wave_arp(x, ad)
                return
        self._wave_arp(x, ad)

    def _filter_resonance(self) -> None:
        a = (self.r(0x00FF) << 1) & 0xFF
        if a == 0:
            a = (a + 1) & 0xFF
        self.w(0x02BF, a)
        xc9 = self.r(0x02C9)
        bf = self.r(0x02BF)
        if (xc9 & bf) == 0:
            self.w(SID_REG_BASE + 0x17, (xc9 + bf) & 0xFF)

    def _filter_walk_1c33(self, x: int) -> None:
        self._filter_cutoff_write(x, self.r(self.t_filter + 0))

    def _filter_walk_1c3e(self, x: int, yy: int) -> None:
        ny = (yy - 6) & 0xFF
        val = (self.vget(0x02C0, x) + self.r(self.t_filter + ny)) & 0xFF
        self._filter_cutoff_write(x, val)

    def _filter_cutoff_write(self, x: int, val: int) -> None:
        self.vset(0x02C0, x, val & 0xFF)
        self.w(SID_REG_BASE + 0x16, val & 0xFF)

    def _wave_arp(self, x: int, ad: int) -> None:
        ac = self.r(0x02AC)
        if (ac & 0x10) == 0:  # 1cc6
            if (ac & 0x80) != 0:  # hard freq set
                if self.vget(0x0299, x) < 2:
                    self.w(SID_REG_BASE + 1 + ad, 0x48)
                    self.w(SID_REG_BASE + 0 + ad, 0)
                    self.vset(0x02D0, x, 0x81)
                    self._lab_1d35(x)
                    return
                self.w(SID_REG_BASE + 0 + ad, self.vget(0x0293, x))
                self.w(SID_REG_BASE + 1 + ad, self.vget(0x028D, x))
                self.vset(0x02D0, x, self.vget(0x0284, x) & 0xFE)
            if (ac & 4) != 0:
                self._arp_delay(x, ad)
            self._lab_1d35(x)
            return
        self._wave_program(x, ad)

    def _arp_delay(self, x: int, ad: int) -> None:
        nb8 = _s8(self.vget(0x02B8, x) - 1)
        self.vset(0x02B8, x, nb8 & 0xFF)
        if nb8 < 0:
            self.vset(0x02B8, x, 2)
        delay = self.r(self.t_arpdelay + self.vget(0x02B8, x))
        self.w(0x0041, delay)
        noteidx = (self.vget(0x0287, x) + _s8(delay)) & 0xFF
        self._lab_1d25(ad, noteidx)

    def _lab_1d25(self, ad: int, noteidx: int) -> None:
        self.w(SID_REG_BASE + 0 + ad, self.r(self.freq_lo + noteidx))
        self.w(SID_REG_BASE + 1 + ad, self.r(self.freq_hi + noteidx))

    def _wave_program(self, x: int, ad: int) -> None:
        d2aa = self.r(0x02AA)
        y = d2aa & 0x0F
        self.w(self.a_wave_self + 0, self.r(self.t_waveptr + 0 + y))
        self.w(self.a_wave_self + 1, self.r(self.t_waveptr + 2 + y))
        self.w(self.a_wave_self + 8, self.r(self.t_waveptr + 4 + y))
        self.w(self.a_wave_self + 9, self.r(self.t_waveptr + 6 + y))
        c299 = self.vget(0x0299, x)
        if c299 >= 0x0F:
            self._lab_1d35(x)
            return
        idx = (c299 - 1) & 0xFF
        self.vset(0x02D0, x, self.r(self.t_wavectrl + idx))
        pitch = self.r(self.t_wavepitch + idx)
        self.w(0x02BF, pitch)
        if (d2aa & 0x10) != 0:
            noteidx = (self.vget(0x0287, x) + _s8(pitch)) & 0xFF
            self._lab_1d25(ad, noteidx)
        else:
            self.w(SID_REG_BASE + 1 + ad, (pitch + 0x0D) & 0xFF)
            self.w(SID_REG_BASE + 0 + ad, 0)
        self._lab_1d35(x)


def iter_frames(
    song: Song, max_frames: int = 50 * 60
) -> Iterator[List[Tuple[int, int]]]:
    """Yield each frame's ``(reg, val)`` SID register writes for ``song``.

    The FC player loops forever (a sequence ``$ff`` restarts each voice), so
    ``max_frames`` bounds the playback (default one minute at 50 Hz).
    """
    player = Player(song)
    for _ in range(max_frames):
        yield player.play_frame()


def render_grid(song: Song, nframes: int) -> List[List[int]]:
    """Render ``nframes`` of ``song`` to a forward-filled per-frame register grid.

    One row per frame, each of the 25 SID registers holding its last-written
    value (forward fill); pulse-width-high registers are masked to their 4 SID-
    significant bits -- the same framing the ``deplayroutine`` oracle uses, so the
    grid is byte-comparable.
    """
    rows: List[List[int]] = []
    cur = [0] * NREG
    for writes in iter_frames(song, max_frames=nframes):
        for reg, val in writes:
            cur[reg] = (val & 0x0F) if reg in constants.PW_HI_REGS else val
        rows.append(cur[:])
    return rows
