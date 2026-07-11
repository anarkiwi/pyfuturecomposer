# Oracle testing

`tests/test_oracle_hvsc.py` renders a tune with `FutureComposerPlayer` and asserts
the per-frame SID register grid matches [`sidtrace`](https://github.com/anarkiwi/sidtrace)
— a patched `sidplayfp` run in the `anarkiwi/sidtrace` Docker image — frame for
frame. It reuses `pysidtracker.make_oracle_fixtures`, so the resolve/render/frame/
compare machinery is the shared base (see the base package's
[oracle-testing docs](https://github.com/anarkiwi/pysidtracker/blob/main/docs/oracle-testing.md)).

```python
from pyfuturecomposer import FutureComposerPlayer

def _render(data, nframes):
    return FutureComposerPlayer(data).render_grid(nframes)
```

- **Marked `oracle`**, excluded from the default suite (`-m 'not oracle'`); a
  dedicated CI job runs `pytest -m oracle -n auto` with Docker.
- **Never skipped**: an unavailable tune raises `TuneFetchError` and a failed
  oracle render raises `SidtraceUnavailable`, so a broken download or render
  fails the test instead of hiding a regression.
- HVSC `.sid` files are copyright works: downloaded to `.oracle-cache/` (or a
  local `$HVSC` tree), never committed.

## Coverage

This player is a faithful transcription of **one** MoN/FutureComposer build (the
`We R Da Best (tune 2)` reference), so byte-exact playback is confirmed for that
build. Other FC builds place their inline tables at different offsets; recognition
of the broader family is covered by `tests/test_corpus.py`, not this oracle.
