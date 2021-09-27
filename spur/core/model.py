import logging
import json
import importlib

from simpy import Environment
from networkx import MultiGraph

from spur.core.train import Train
from spur.core.jitter import NoJitter
from spur.core.route import Route

# Set up the logging module for errors and debugging
logger = logging.getLogger(__name__)


class SimLogFilter(logging.Filter):
    def __init__(self, model, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.model = model

    def filter(self, record) -> bool:
        record.now = self.model.now
        return True


class Model(Environment):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.G = MultiGraph()
        self._trains = {}
        self._routes = {}  # Used as a container to keep track of possible routes

        # Set up logging environment for the simulation output
        self.simLog = logging.getLogger("sim")
        self.simLog.setLevel(logging.DEBUG)

        # Set up stout output and formatting
        sh = logging.StreamHandler()
        sh.setLevel(logging.INFO)
        sh.addFilter(SimLogFilter(self))
        simFormatter = logging.Formatter(
            "%(now)-5d %(name)-35s  %(message)s", style="%"
        )
        sh.setFormatter(simFormatter)
        self.simLog.addHandler(sh)

        fh = logging.FileHandler("log/sim.log", mode="w")
        fh.setLevel(logging.DEBUG)
        fh.addFilter(SimLogFilter(self))
        simFileFormatter = logging.Formatter(
            "%(now)-5d %(levelname)-8s %(name)-30s  %(message)s", style="%"
        )
        fh.setFormatter(simFileFormatter)
        self.simLog.addHandler(fh)

        logger.info("Model setup complete!")

    @property
    def trains(self):
        return self._trains

    @property
    def components(self):
        return [d["c"] for u, v, d in self.G.edges(data=True)]

    def component_dictionary(self):
        components = [d["c"] for u, v, d in self.G.edges(data=True)]
        d = dict()
        for c in components:
            d[c.uid] = c
        return d

    def add_component(self, component_type, u, v, key, *args, **kwargs):
        # Initialize a brand new component of the type passed
        c = component_type(self, f"{u}-{v}-{key}", *args, **kwargs)
        # Add it to the graph
        self.G.add_edge(u, v, key=key, c=c)
        logger.info(f"Added {c.__name__} {c.uid}")
        return c

    def add_train(self, uid, max_speed, route) -> Train:
        # Initialize a brand new train
        t = Train(self, uid, route, max_speed)
        # Add it to our dictionary of trains
        self.trains[uid] = t
        return t

    def start(self):
        # We go through each train and get it started
        self.simLog.info("Simulation is starting...")
        for key in self.trains.keys():
            self._trains[key].start()

    def run(self, until=None):
        logger.info("Starting model run")
        super().run(until)
        logger.info("Finished model run")

    def components_from_json(self, filepath):
        with open(filepath, "r") as infile:
            components = json.load(infile)

        for c in components:
            component = getattr(
                importlib.import_module("spur.core.component"), c["type"]
            )
            # Check jitter separately.
            if "jitter" in c.keys():
                Jitter = getattr(
                    importlib.import_module("spur.core.jitter"), c["jitter"]["type"]
                )
                jitter = Jitter(**c["jitter"]["args"])
            else:
                jitter = NoJitter()

            self.add_component(
                component, c["u"], c["v"], c["key"], jitter=jitter, **c["args"]
            )

    def routes_from_json(self, filepath):
        with open(filepath, "r") as infile:
            routes = json.load(infile)

        components = self.component_dictionary()
        for r in routes:
            new_route = Route()
            for c in r["components"]:
                if "args" in c:
                    new_route.append(
                        components[f"{c['u']}-{c['v']}-{c['key']}"], **c["args"]
                    )
                else:
                    new_route.append(components[f"{c['u']}-{c['v']}-{c['key']}"])
            self._routes[r["name"]] = new_route

    def trains_from_json(self, filepath):
        with open(filepath, "r") as infile:
            trains = json.load(infile)

        for t in trains:
            self.add_train(
                t["name"], max_speed=t["max_speed"], route=self._routes[t["route"]]
            )
