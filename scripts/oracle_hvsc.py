"""pyfuturecomposer's renderer for the ``pysidtracker.survey`` whole-song HVSC oracle survey.

    PYTHONPATH=scripts python -m pysidtracker.survey run $HVSC tunes.csv \
        --work .hvsc-survey --render oracle_hvsc:render
"""

import numpy as np

from pysidtracker.cadence import cadence_info

from pyfuturecomposer import FutureComposerPlayer, parse
from pyfuturecomposer.errors import FutureComposerParseError
from pyfuturecomposer.variant import variant_of

PLAYER = "^mon/futurecomposer$"


def render(data, song, nframes):
    """Render 1-based ``song`` of a Future Composer ``.sid`` and the build it decoded."""
    tune = parse(data)
    if variant_of(tune).source("build").kind == "default":
        raise FutureComposerParseError("no Future Composer player signature")
    player = FutureComposerPlayer(tune, subtune=song - 1)
    var = player.variant
    info = {
        "layout": var.layout,
        "init": var.init,
        "play": var.play,
        **cadence_info(data, song),
    }
    grid = player.render_grid(nframes)
    return np.asarray(grid, np.int16), info
