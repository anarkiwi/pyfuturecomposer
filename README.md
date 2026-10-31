# pyfuturecomposer

Pure-Python reader and player for
[Future Composer](https://en.wikipedia.org/wiki/Future_Composer) (MoN / Deenen)
C64 SID songs, with per-frame SID register output (byte-exact against the
reference build's oracle) and optional WAV rendering through an emulated SID.

Consumes `.sid` files (PSID/RSID containers) and bare `.prg` images through the
shared [`pysidtracker`](https://github.com/anarkiwi/pysidtracker) base. A code
signature recognises the player. Each build's tables, work area and play entry
are read from the operands of its own play code, and the tune's own init is run
before playback.

## Install

```bash
pip install pyfuturecomposer   # reader/player/reglog, WAV rendering via pylibresidfp
```

## Usage

```python
import pyfuturecomposer as fc

song = fc.read("tune.sid")            # path, bytes, or binary file object; .sid or .prg

# Where this build keeps each table, and how each location was found.
fc.FutureComposerPlayer(song).variant.as_info()   # {"freq_lo": 0x5ab, "freq_lo.src": "detected@$1949", ...}

# The playroutine is a pysidtracker MemPlayer: per-frame SID register writes,
# or a forward-filled 25-register grid.
player = fc.FutureComposerPlayer(song)
for writes in player.iter_frames(50 * 60):
    ...                               # writes: list[(register, value)]
grid = fc.FutureComposerPlayer(song).render_grid(400)

fc.write_prg(song, "tune.prg")        # export a module the FC editor can load
```

See [docs/usage.md](docs/usage.md) for the register grid, register logs, WAV
rendering, and the `pysidtracker info|reglog|wav|export` command line, and
[docs/format.md](docs/format.md) for the format, playroutine, and byte-exact
validation, and [docs/oracle-testing.md](docs/oracle-testing.md) for the
whole-HVSC oracle survey.

## Development

```bash
pip install -e ".[dev]"
./run_tests.sh        # black + pylint + pytest with coverage
```

## License

Apache 2.0 — see [`LICENSE`](LICENSE).
