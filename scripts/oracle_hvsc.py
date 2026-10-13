"""pyfuturecomposer's renderer for the ``pysidtracker.survey`` whole-song HVSC oracle survey.

    PYTHONPATH=scripts python -m pysidtracker.survey run $HVSC tunes.csv \
        --work .hvsc-survey --render oracle_hvsc:render
"""

import numpy as np

from pysidtracker import SidImage
from pysidtracker.cadence import playroutine_cadence
from pysidtracker.registers import PAL_CYCLES_PER_FRAME

from pyfuturecomposer import FutureComposerPlayer, FutureComposerSidParser, parse
from pyfuturecomposer.constants import OFF_SIGNATURE
from pyfuturecomposer.errors import FutureComposerParseError

PLAYER = "^mon/futurecomposer$"


def render(data, song, nframes):
    """Render 1-based ``song`` of a Future Composer ``.sid`` and the build it decoded."""
    tune = parse(data)
    anchor = FutureComposerSidParser().recognize(SidImage.from_bytes(data))
    if anchor is None:
        raise FutureComposerParseError("no Future Composer player signature")
    cadence = playroutine_cadence(data, subtune=song - 1)
    info = {
        "layout": anchor - tune.load - OFF_SIGNATURE,
        "init": tune.init - tune.load,
        "play": tune.play - tune.load,
        "rsid": data[:4] == b"RSID",
        "trigger": cadence.source and cadence.source.value,
        "speed": round(PAL_CYCLES_PER_FRAME / cadence.cycles_per_call),
    }
    grid = FutureComposerPlayer(tune, subtune=song - 1).render_grid(nframes)
    return np.asarray(grid, np.int16), info
