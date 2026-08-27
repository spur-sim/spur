"""Toronto Subway Line 4 Simulation Example

This script contains a minimum working example simulating the movement
of subway trains in an idealized version of Line 4. It is designed
as an example of the inputs and outputs required to create a working
simulation model.

This script requires the `spur` package to be installed correctly,
and for the approprate data inputs to be placed in a subfolder called
`line4_data`.
"""

import logging
import os

from spur.core import Model
from spur.io.formats import (
    read_components_json,
    read_routes_json,
    read_tours_json,
    read_trains_json,
)

# Show simulation output on stdout - the library itself no longer configures
# any logging output, so the embedding application (this script) does it.
logging.basicConfig(level=logging.INFO)

base_path = "line4_data"

# The library no longer creates its own log directory - opt-in file logging
# is the caller's responsibility, including making sure the path exists.
os.makedirs("log", exist_ok=True)

m = Model(sim_log_file="log/sim.log", agent_log_file="log/agent.log")
m.add_components(read_components_json(os.path.join(base_path, "components.json")))
m.add_routes_and_tours(
    read_routes_json(os.path.join(base_path, "routes.json")),
    read_tours_json(os.path.join(base_path, "tours.json")),
)
m.add_trains(read_trains_json(os.path.join(base_path, "trains.json")))

m.start()
m.run(until=36900)
