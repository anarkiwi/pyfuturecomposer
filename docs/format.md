# Future Composer format

## Overview

Future Composer (MoN / Deenen) is a C64 SID music system. `pyfuturecomposer`
parses a Future Composer tune into a typed song model and runs the playroutine
to produce byte-exact per-frame SID register output.

## Container and detection notes

Tunes are consumed as `.sid` (PSID/RSID) containers or bare `.prg` images
through the shared [`pysidtracker`](https://github.com/anarkiwi/pysidtracker)
base. The player is relocatable, so it is located by its code signature rather
than by the container header; packed/relocating builds are detected by running
the tune's init in a 6502 emulator. Container headers are not trusted.

## Data model

`fc.read` / `fc.parse` return a `Song`: the tempo divider, the per-voice
sequence and pattern opcode streams, the instrument records, and the
wave/arp/pulse-width/filter tables the playroutine walks per frame.

## Writing back (editor-loadable export)

The FutureComposer editor's native module is the driver code plus the inline
song data saved as a plain C64 program (two-byte load address + image), so
:func:`pyfuturecomposer.to_prg` re-emits exactly that and a canonical build
(load `$1800`, play `$1806`) loads straight back into the editor. There is no
separate data-only container (unlike Amiga Future Composer's `SMOD`).
:func:`pyfuturecomposer.to_sid` re-wraps the same image in a PSID, preserving the
entry points and metadata for a byte-exact model round-trip. Relocated rips are
written verbatim at their own load address; the 6502 code carries absolute
operands, so this exporter does not re-relocate them to `$1800`.

## Player and playback notes

`FutureComposerPlayer` is a `pysidtracker.MemPlayer`: the base owns the flat
64 KiB 6502 memory, the `$D400` register snapshot/diff, and the `iter_frames` /
`render_grid` drivers, while this package implements only FC's `_init` (clear the
work bytes) and `_frame` (one tick). `_frame` is a faithful integer transcription
of Future Composer's `entry_1806` 6502 play routine: the tempo divider, the
per-voice DEC-duration row advance, the opcode-stream SEQUENCE + PATTERN walks,
and the dense per-frame modulation engine (slide-target vibrato / portamento, the
`$E0` glide, a 16-bit pulse-width sweep, the filter-cutoff program and the
wave / arp tables).

`iter_register_writes(song, max_frames=..) -> (clock, reg, val)` is the shared
`py*` register-log surface (via `pysidtracker.reglog.register_writes_from_player`,
matching `pymusicassembler` / `pygoattracker`).

This is a transcription of a single MoN/FutureComposer player build -- the one
derived from the reverse-engineering reference tune *We R Da Best (tune 2)*
(Warren Pilbrough / Jade Tiger). `render_grid` reproduces the `sidtrace`
`sidplayfp` register oracle for that build byte-exact (see
[oracle testing](oracle-testing.md) and `tests/test_oracle_hvsc.py`). Detection
of the broader FC family -- both player-code signatures, every load address, PSID
and RSID -- is validated across a ~150-tune HVSC corpus in `tests/test_corpus.py`;
other player builds place their inline tables at different offsets and are not
reproduced by this transcription.

## References

- [Future Composer](https://en.wikipedia.org/wiki/Future_Composer) (MoN /
  Deenen).
- `preframr-sidtrace` register oracle; `deplayroutine` generic interpreter.
- [pyresidfp](https://pypi.org/project/pyresidfp/) — reSIDfp SID emulation
  (WAV render).
- [`pysidtracker`](https://github.com/anarkiwi/pysidtracker) — shared
  container/image/detection base.
