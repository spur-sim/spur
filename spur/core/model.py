"""Contains classes describing the model controller"""

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
    """The model class

    Attributes
    ----------
    G : `NetworkX.MultiGraph`
        The graph representation of the model system
    simLog : `logging.Logger`
        The logging component of the model
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.G = MultiGraph()
        self._trains = {}
        self._routes = {}  # Used as a container to keep track of possible routes

        # Set up logging environment for the simulation output
        self.simLog = logging.getLogger("sim")
        self.simLog.setLevel(logging.INFO)

        # Set up stout output and formatting
        sh = logging.StreamHandler()
        sh.setLevel(logging.INFO)
        sh.addFilter(SimLogFilter(self))
        simFormatter = logging.Formatter(
            "%(now)-6d %(name)-35s  %(message)s", style="%"
        )
        sh.setFormatter(simFormatter)
        self.simLog.addHandler(sh)

        # Set up logfile output and formatting
        fh = logging.FileHandler("log/sim.log", mode="w")
        fh.setLevel(logging.INFO)
        fh.addFilter(SimLogFilter(self))
        simFileFormatter = logging.Formatter(
            "%(now)-6d %(levelname)-8s %(name)-30s  %(message)s", style="%"
        )
        fh.setFormatter(simFileFormatter)
        self.simLog.addHandler(fh)

        # Set up logfile output and formatting for debug
        dfh = logging.FileHandler("log/debug.log", mode="w")
        dfh.setLevel(logging.DEBUG)
        dfh.addFilter(SimLogFilter(self))
        simFileFormatter = logging.Formatter(
            "%(now)-6d %(levelname)-8s %(name)-30s  %(message)s", style="%"
        )
        dfh.setFormatter(simFileFormatter)
        self.simLog.addHandler(dfh)

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
        """Add a component to the model network

        Parameters
        ----------
        component_type : str
            The class name (e.g. `SimpleStation` of the component to add)
        u : str
            The first node end of the component
        v : str
            The second node end of the component
        key : str
            The key of the component
        """

        # Initialize a brand new component of the type passed
        c = component_type(self, f"{u}-{v}-{key}", *args, **kwargs)
        # Add it to the graph
        self.G.add_edge(u, v, key=key, c=c)
        logger.debug(f"Added {c.__name__} {c.uid}")
        return c

    def add_train(self, uid, max_speed, route) -> Train:
        """Add a train to the model

        Parameters
        ----------
        uid : mixed
            Unique ID of the object
        max_speed : int
            The maximum speed of the train
        route : `Route`
            The route for the train to follow

        Returns
        -------
        Train
            The initialized and added train object
        """

        # Initialize a brand new train
        t = Train(self, uid, route, max_speed)
        # Add it to our dictionary of trains
        self.trains[uid] = t
        return t

    def start(self):
        """Start the model

        Starting the model activates all agents and components to be ready for running.
        """

        # We go through each train and get it started
        self.simLog.info("Simulation is starting...")
        for key in self.trains.keys():
            self._trains[key].start()
        self.simLog.info(f"Activated {len(self.trains.keys())} trains")

    def run(self, until=None):
        """Run the model for a specified time

        Parameters
        ----------
        until : int, optional
            The number of steps to run the model for, by default None which runs
            until all components finished.
        """
        self.simLog.info("Starting model run")
        super().run(until)
        self.simLog.info("Finished model run")

    @classmethod
    def from_project_dictionary(cls, project):
        model = cls()
        model.add_components_from_list(project["components"])
        model.add_routes_from_list(project["routes"])
        model.add_trains_from_list(project["trains"])
        return model

    def add_components_from_list(self, components):
        """Add a list of components to the network

        Parameters
        ----------
        components : list
            The list of components to add
        """

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

    def add_components_from_json_file(self, filepath):
        """Add a set of components from a formatted JSON file

        Parameters
        ----------
        filepath : str
            The path to the JSON file containing components.
        """

        with open(filepath, "r") as infile:
            components = json.load(infile)
        self.add_components_from_list(components)

    def add_routes_from_list(self, routes):
        """Add routes to the model from a list

        Parameters
        ----------
        routes : list
            A list of `Route` objects to add
        """

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

    def add_routes_from_json_file(self, filepath):
        """Add a set of routes from a JSON file

        Parameters
        ----------
        filepath : str
            The path to the JSON file
        """

        with open(filepath, "r") as infile:
            routes = json.load(infile)
        self.add_routes_from_list(routes)

    def add_trains_from_list(self, trains):
        """Add trains to the model from a list of train objects

        Parameters
        ----------
        trains : list
            A list of train objects
        """

        for t in trains:
            self.add_train(
                t["name"], max_speed=t["max_speed"], route=self._routes[t["route"]]
            )

    def add_trains_from_json_file(self, filepath):
        """Add a set of trains to the model from a formatted JSON file

        Parameters
        ----------
        filepath : str
            The path to the JSON file
        """

        with open(filepath, "r") as infile:
            trains = json.load(infile)
        self.add_trains_from_list(trains)
