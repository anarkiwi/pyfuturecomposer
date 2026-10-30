# Future Composer format

## Overview

Future Composer (MoN / Deenen) is a C64 SID music system. `pyfuturecomposer`
parses a Future Composer tune into a typed song model and runs the playroutine
to produce byte-exact per-frame SID register output.

## Container and detection notes

Tunes are consumed as `.sid` (PSID/RSID) containers or bare `.prg` images
through the shared [`pysidtracker`](https://github.com/anarkiwi/pysidtracker)
base. The header's load/init/play addresses are used. A bare `.prg` falls back
to init = load and play = load + 6. `recognize` finds the player by
`layout.SIGNATURE`. This is a `SitePattern` with two alternatives: `row`, the
per-voice row/duration advance, and `filter`, the `$D417` filter store. It
reports which alternative matched, and every absolute operand is wildcarded.

## Build variants

Future Composer builds share one play routine. They differ in where the tables,
the per-voice work area and the self-modified operands sit, and in small code
inserts that shift everything after them. `pyfuturecomposer.layout.detect`
reads each address from the code that uses it and returns a
`pysidtracker.Variant`. Each facet has a value and a source:
`detected@$addr` for the code site it was read from, or `default` for the
reference build's value.

- `signature`, `layout`: the recogniser alternative that matched, and its
  offset from where the reference build has that fragment.
- `init`, `play`: the entry points as offsets from load. `play` is detected when
  `layout.PLAY_CHAIN` matches the play entry. This `RoutineChain` reads the
  state-byte test and then the tick it branches to.
- `work`: the absolute base of the per-voice work area (`$0278` in the
  reference build), from the state byte the play entry tests.
- `tempo` (the speed byte), `voice_base`, `seq_lo`/`seq_hi`, `pat_ptr`, `freq_lo`/`freq_hi`,
  `instr`, `mod`, `pw_step`, `wave_arp`, `filter`, `wave_prog_ptr`,
  `arp_delay`: the table bases, from the operands of their table-indexed loads
  (`layout.SITES`).
- `slide`, `pw_carry`, `wave_ctrl`, `wave_pitch`, `filt_lo`/`filt_hi`: the
  operands the player rewrites at run time.

`FutureComposerPlayer.variant` is the variant it plays with. `Variant.as_info()`
is the survey `info`, and the `pysidtracker` format registration exposes it to
`pysidtracker variant census`.

## Data model

`fc.read` / `fc.parse` return a `Song`: the raw C64 `image` (player code and
inline song data), its `load` address, the `init` / `play` entry points, and the
header `name` / `author` / `released` strings. The song data stays in the image;
see Song streams for how it is parsed.
The player reads sequences, patterns, instruments and modulation tables from
there, at the addresses the variant gives.

## Song streams

`pyfuturecomposer.streams.GRAMMAR` is the `futurecomposer.lark` byte grammar
(`pysidtracker.ByteGrammar`). `streams.streams(song)` reads, from the tune's
post-init memory, the three voice sequences, every pattern those sequences name
and every instrument those patterns select; `pysidtracker grammar TUNE` lists
them. `read(path, validate=True)` raises `SidParseError` for bytes that are not
one stream. Validation is off by default: builds whose tables the layout does
not locate (#13, #17) do not parse.

A sequence is read through its voice pointer (`seq_lo`/`seq_hi`) and ends at
`$FE` (the song stops) or `$FF` (the voice restarts at its first byte). It must
name at least one pattern.

| Sequence byte | Meaning |
| --- | --- |
| `$00`-`$3F` | play pattern `byte` |
| `$40`-`$7F` | repeat the next pattern `byte & $3F` more times |
| `$80`-`$FD` | transpose: add `byte & $1F` (0-31) to every following note index |
| `$FE` | end of song |
| `$FF` | loop this voice |

A pattern is read through the interleaved `pat_ptr` table (entry `id * 2`) and
ends at `$FF` after a command. An `$FF` first byte is instead a row marker.

| Pattern byte | Meaning |
| --- | --- |
| `$00`-`$7F` | note index |
| `$80`-`$BF` | note duration `byte & $3F` |
| `$C0`-`$DF` | select instrument `byte & $1F` |
| `$E0`-`$EF` | slide command, then one argument byte |
| `$F0`-`$FE` | row marker: the next byte is the note, and the instrument is not reloaded |
| `$FF` | end of pattern |

An instrument is an 8-byte record at `instr + id * 8`: pulse control and
high nibble, waveform, attack/decay, sustain/release, aux, vibrato control,
pulse-width control, master control.

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

`FutureComposerPlayer` is a `pysidtracker.playspec.SpecPlayer`. It runs the
tune's own init on the emulated 6502, then each play call runs
`src/pyfuturecomposer/specs/futurecomposer.play` on the memory the init left.
The spec states Future Composer's `entry_1806` play routine: the tempo divider
(machine `clock`), and per voice (machine `voice[x]`) the DEC-duration row
advance, the opcode-stream sequence and pattern walks, and the per-frame
modulation engine. That engine covers slide-target vibrato and portamento, the
`$E0` glide, a 16-bit pulse-width sweep, the filter-cutoff program and the
wave / arp tables. `layout.detect` supplies the spec's `layout` block
(`player.binding`): each table and self-modified operand address, and the work
base. The work area, the self-modified operands and the zero-page scratch
bytes are cells in the spec, so after every call the full 64 KiB outside the
stack page equals the tune's own 6502 run for the reference build.

The spec opens a `stream` with a grammar for each sequence, pattern and
instrument it walks. `FutureComposerPlayer(song, validate=True)` parses each
against `streams.GRAMMAR` and raises `FutureComposerParseError` for bytes that
are not one stream, such as a pattern with no `$FF` terminator.

`pysidtracker playspec check src/pyfuturecomposer/specs/futurecomposer.play`
type-checks the spec. A loop that runs past its bound, such as a sequence that
never reaches a pattern, raises `FutureComposerParseError`.

`iter_register_writes(song, max_frames=..) -> (clock, reg, val)` is the shared
`py*` register-log surface (via `pysidtracker.reglog.register_writes_from_player`,
matching `pymusicassembler` / `pygoattracker`). The player sets `MASK_PW_HI`, so
both it and the grid carry only the low nibble of the pulse-width-high registers
(`$D403/$D40A/$D411`), the bits the SID uses.

The transcription follows the play routine of the reference tune *We R Da
Best (tune 2)* (Warren Pilbrough / Jade Tiger). `render_grid` reproduces the
`sidtrace` `sidplayfp` register oracle for it byte-exact over the whole song (see
[oracle testing](oracle-testing.md) and `tests/test_oracle_hvsc.py`). Builds
whose play code matches this routine are placed by their variant. Builds with
code paths the transcription does not have (for example V3.0/V3.1, #17) are not
reproduced. `tests/test_corpus.py` checks detection over a ~150-tune HVSC
corpus.

## References

- [Future Composer](https://en.wikipedia.org/wiki/Future_Composer) (MoN /
  Deenen).
- `preframr-sidtrace` register oracle; `deplayroutine` generic interpreter.
- [pyresidfp](https://pypi.org/project/pyresidfp/) — reSIDfp SID emulation
  (WAV render).
- [`pysidtracker`](https://github.com/anarkiwi/pysidtracker) — shared
  container/image/detection base.
