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
  state-byte test and then the tick it branches to. The entry is tried at the
  header's play address, where any `JMP` trampolines there lead, and at
  `load + 6`; a build whose init patches the trampoline is detected on the
  memory its own init leaves.
- `state`: whether the entry tests the state byte (`$02CB` in the reference
  build). A build that jumps straight to the tick has none, matches
  `layout.TICK_CHAIN` and takes its work base from the countdown byte.
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
them. `read(path)` and `parse(data)` raise `SidParseError` for bytes that are not
one stream (`validate=False` skips the check). The `info` and `export` commands
and the format's parser object read without it, so they still work on a tune of
a build this grammar does not describe (#13, #17). The static listing leaves out
patterns of an unterminated sequence, whose reach is unknown, and patterns whose
pointer is not set yet. Validating runs the tune's own init, so a bare `.prg`,
which has none, is checked as loaded.

`pysidtracker equiv A B` compares two tunes by these streams, so two containers
of one song are equal and a changed note is reported as a diff. The format's
snapshot probes are the `.prg` and `.sid` exports and the variant `info`.
Tables that reach the C64 I/O area are rejected, because a C64 reads chips
there instead of RAM.

A sequence is read through its voice pointer (`seq_lo`/`seq_hi`) and ends at
`$FE` (the song stops) or `$FF` (the voice restarts at its first byte). The
position byte is 8 bits, so 256 steps with no terminator are also one sequence:
the player wraps to the first. A list that ends in `$FF` or has no terminator
must name at least one pattern; a list that is only `$FE` is a voice that stops
the song at once.

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
`src/pyfuturecomposer/specs/futurecomposer.play`. The spec states the format, not
the 6502 routine:

- the tempo is a counter (`countdown`) that wraps to the speed byte and fires the
  `row` event;
- on a row each voice counts its note's duration down (`left`); out of rows it
  fires `note`, which reads the next note: the orderlist is a cursor over the
  voice's sequence (transposes and repeats are decoded as they are passed, a
  pattern byte, `$FE` and `$FF` stop it) and the pattern a second cursor whose
  commands set the slide, instrument and duration until a note starts the sound;
  the end of a pattern fires `pattern_end`, which counts the repeat down and
  moves the orderlist on;
- every other call the voice plays its instrument's modulation (`modulate`):
  vibrato or the arpeggio steps, slide, pulse-width sweep and jitter, the filter
  program, and the waveform and pitch programs.

Every play variable (the tempo counter, positions, durations, slide, pulse width,
vibrato phase, filter owner, song state) is spec `state`, no address, started from the
byte the tune's init left in the player's work area.
`pyfuturecomposer.player.binding(song)` is the spec's `layout`: the addresses of the
build's tables (`layout.detect`) and the `init_<variable>` values read from the memory
after the init. A play variable is read and set with `SpecPlayer.state(name)` /
`set_state(name, value)`: `voice[x].seqpos`, `voice[x].left`, `play_state` (`2` once
the song has ended, `1` restarts the voices), and so on; `player.finished` is
`play_state == 2`. `pyfuturecomposer.player.play_variables` names the work-area
byte of each, for comparing a run against the tune's own 6502.

The binder refuses a build it has not placed, with `FutureComposerParseError`: one whose
work area lies over its speed or voice-base table, or whose play routine does not start at
the entry the spec stands in for, so that the real player runs beside the spec
(`tests/fixtures/fc_refused.txt` lists the HVSC tunes). The play variables that data can
reach are read as the variable: a pulse program row past the table's end over the vibrato
shift and depth (`pw_wild`), and a null pattern pointer over the arpeggio scratch byte and
the voice's pointers and index in page zero (`arp_zp`, `order_zp`, `pat_zp`, `voice_zp`).

A sequence that never reaches a pattern or a pattern that never reaches a note
runs past the spec's bounded loop and raises `FutureComposerParseError`.
`pysidtracker playspec check src/pyfuturecomposer/specs/futurecomposer.play`
type-checks the spec.

What a pattern byte means depends on what precedes it. After a slide command an
instrument, a duration or a note may follow; after an instrument a duration or a
note. Any other byte there is the note, so `$C1 $C2` plays note `$C2`.

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
- [pylibresidfp](https://pypi.org/project/pylibresidfp/) — libresidfp SID emulation
  (WAV render).
- [`pysidtracker`](https://github.com/anarkiwi/pysidtracker) — shared
  container/image/detection base.
