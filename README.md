# pyfuturecomposer

Pure-Python reader and player for
[Future Composer](https://en.wikipedia.org/wiki/Future_Composer) (MoN / Deenen)
C64 SID songs, with byte-exact per-frame SID register output and optional WAV
rendering through an emulated SID.

Consumes `.sid` files (PSID/RSID containers) and bare `.prg` images through the
shared [`pysidtracker`](https://github.com/anarkiwi/pysidtracker) base: the
relocatable Future Composer player is located by its code signature and
packed/relocating builds are detected by running the tune's init — container
headers are not trusted.

## Install

```bash
pip install pyfuturecomposer          # reader/player/reglog (pure stdlib)
pip install pyfuturecomposer[audio]   # + WAV rendering via pyresidfp
```

## Usage

```python
import pyfuturecomposer as fc

song = fc.read("tune.sid")            # path, bytes, or binary file object; .sid or .prg

# Per-frame SID register writes the playroutine emits each frame.
for writes in fc.iter_frames(song, max_frames=50 * 60):
    ...                               # writes: list[(register, value)]

fc.write_prg(song, "tune.prg")        # export a module the FC editor can load
```

See [docs/usage.md](docs/usage.md) for the register grid, register logs, WAV
rendering, and the command line, and [docs/format.md](docs/format.md) for the
format, playroutine, and byte-exact validation.

## Development

```bash
pip install -e ".[dev]"
./run_tests.sh        # black + pylint + pytest with coverage
```

## License

Apache 2.0 — see [`LICENSE`](LICENSE).
