"""Toronto Subway Line 4 Simulation Example

This script contains a minimum working example simulating the movement
of subway trains in an idealized version of Line 4. It is designed
as an example of the inputs and outputs required to create a working
simulation model.

This script requires the `spur` package to be installed correctly,
and for the approprate data inputs to be placed in a subfolder called
`line4_data`.
"""

import os
import sys

from spur.core import Model

base_path = "line4_data"

m = Model()
m.add_components_from_json_file(os.path.join(base_path, "components.json"))
m.add_routes_from_json_file(os.path.join(base_path, "routes.json"))
m.add_trains_from_json_file(os.path.join(base_path, "trains.json"))

m.start()
m.run(until=36900)
