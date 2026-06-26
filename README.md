# pyfuturecomposer

A standalone, pure-Python **reader and player** for
[Future Composer](https://en.wikipedia.org/wiki/Future_Composer) (MoN / Deenen)
C64 SID songs. It parses a Future Composer tune into a typed song model and runs
the playroutine to produce byte-exact per-frame SID register output, with an
optional WAV render through an emulated SID.

The player is a faithful integer transcription of Future Composer's `entry_1806`
6502 play routine (the tempo divider, the per-voice DEC-duration row advance, the
opcode-stream SEQUENCE + PATTERN walks, and the dense per-frame modulation engine:
slide-target vibrato / portamento, the `$E0` glide, a 16-bit pulse-width sweep, the
filter-cutoff program and the wave / arp tables). It reproduces the
`preframr-sidtrace` register oracle of the reverse-engineering reference tune
*We R Da Best (tune 2)* (Warren Pilbrough / Jade Tiger) byte-exact.

Read/play/register-log is **pure stdlib**; only WAV rendering needs the optional
`audio` extra (pyresidfp).

```bash
pip install pyfuturecomposer          # reader/player/reglog
pip install pyfuturecomposer[audio]   # + WAV rendering via pyresidfp
```

## Quick start

```python
import pyfuturecomposer as fc

song = fc.read("tune.sid")            # PSID/.sid or bare .prg

# Per-frame SID register writes (the writes the playroutine emits each frame).
for writes in fc.iter_frames(song, max_frames=50 * 60):
    ...                               # writes: list[(register, value)]

# Forward-filled 25-register-per-frame snapshot grid (the oracle form).
grid = fc.render_grid(song, nframes=400)

# Register log (clock reg val triples), and WAV via an emulated SID.
fc.write_reglog(fc.iter_register_writes(song, max_frames=2500), "tune.reglog")
fc.render_wav(song, "tune.wav", seconds=30)   # needs the audio extra
```

## Command line

```bash
pyfuturecomposer info   tune.sid
pyfuturecomposer reglog tune.sid tune.reglog --seconds 30
pyfuturecomposer wav    tune.sid tune.wav --seconds 30 --model 8580
```

## Register-surface convention

`iter_register_writes(song, max_frames=..) -> (clock, reg, val)` is the shared
`py*` register-log surface (matching `pymusicassembler` / `pygoattracker`), so the
output cross-validates byte-exact against the `deplayroutine` generic interpreter
and the `preframr-sidtrace` oracle.

## Tests

Test tunes are HVSC copyright works and are **never** committed; they are fetched
on demand into a gitignored cache (`scripts/fetch_tunes.py`), and the byte-exact
player test validates against a committed frozen oracle grid when the
`preframr-sidtrace` binary (`$SIDTRACE_BIN`) is unavailable.

```bash
./run_tests.sh          # black + pylint + pytest with coverage
```

## License

Apache-2.0. See `LICENSE`.
