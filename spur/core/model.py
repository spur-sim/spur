"""Contains classes describing the model controller"""

import logging
import json
import importlib

from simpy import Environment
from networkx import MultiGraph

from spur.core.train import Train
from spur.core.jitter import NoJitter
from spur.core.route import Route
from spur.core.tour import Tour

from spur.core.exception import NotUniqueIDError, InputMismatchError

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

    def __init__(self, debug=False, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.G = MultiGraph()
        self._trains = {}
        self._tours = {}  # Used as a container to keep track of possible tours
        self._collections = {}  # Used as a container to keep track of all collections

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
        if debug == True:
            dfh = logging.FileHandler("log/debug.log", mode="w")
            dfh.setLevel(logging.DEBUG)
            dfh.addFilter(SimLogFilter(self))
            simFileFormatter = logging.Formatter(
                "%(now)-6d %(levelname)-8s %(name)-30s  %(message)s", style="%"
            )
            dfh.setFormatter(simFileFormatter)
            self.simLog.addHandler(dfh)

        self.simLog.info("Model setup complete!")

    @property
    def trains(self):
        return self._trains

    @property
    def components(self):
        return [d["c"] for u, v, d in self.G.edges(data=True)]

    @property
    def collections(self):
        return self._collections

    def _uid_unique(self, uid):
        if uid in self._trains.keys() or uid in self._tours.keys():
            return False
        else:
            return True

    def component_dictionary(self):
        d_out = dict()
        for u, v, d in self.G.edges(data=True):
            d_out[d["c"].uid] = {"c": d["c"], "u": u, "v": v}
        return d_out

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
        self.simLog.debug(f"Added {c.__name__} {c.uid}")
        return c

    def add_train(self, uid, max_speed, tour) -> Train:
        """Add a train to the model

        Parameters
        ----------
        uid : mixed
            Unique ID of the object
        max_speed : int
            The maximum speed of the train
        tour : `Tour`
            The tour for the train to follow

        Returns
        -------
        Train
            The initialized and added train object
        """

        # Initialize a brand new train
        t = Train(self, uid, tour, max_speed)
        # Add it to our dictionary of trains
        self.trains[uid] = t
        return t

    def start(self):
        """Start the model

        Starting the model activates all agents and components to be ready for running.
        """

        # We go through each train and get it started
        self.simLog.info("Model initialization started")
        for key in self.trains.keys():
            self._trains[key].start()
        self.simLog.info(f"Activated {len(self.trains.keys())} trains")
        self.simLog.info("Model initialization finished successfully")

    def run(self, until=None):
        """Run the model for a specified time

        Parameters
        ----------
        until : int, optional
            The number of steps to run the model for, by default None which runs
            until all components finished.
        """
        if self.now > 0:
            self.simLog.info("Model resumed")
        else:
            self.simLog.info("Model started")
        super().run(until)
        self.simLog.info("Model stopped")

    @classmethod
    def from_project_dictionary(cls, project):
        model = cls()
        model.add_components_from_list(project["components"])
        model.add_routes_and_tours_from_lists(project["routes"], project["tours"])
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

            # Check if component belongs to a collection
            if "collection" in c.keys():
                collection_id = f"{c['collection']['type']}-{c['collection']['key']}"
                if collection_id in self.collections:
                    # If collection instance has already been created, look it up
                    collection = self.collections[collection_id]
                else:
                    # Otherwise, create a new collection and save it
                    Collection = getattr(
                        importlib.import_module("spur.core.collection"),
                        c["collection"]["type"],
                    )
                    collection = Collection(model=self, uid=collection_id)
                    self.collections[collection_id] = collection
            else:
                collection = None

            self.add_component(
                component,
                c["u"],
                c["v"],
                c["key"],
                jitter=jitter,
                collection=collection,
                **c["args"],
            )

    def add_components_from_json_file(self, filepath):
        """Add a set of components from a formatted JSON file

        Parameters
        ----------
        filepath : str
            The path to the JSON file containing components.
        """
        self.simLog.info("Loading components from JSON file")
        with open(filepath, "r") as infile:
            components = json.load(infile)
        self.add_components_from_list(components)

    def add_routes_and_tours_from_lists(self, routes, tours):
        """Add routes and tours to the model from lists

        Parameters
        ----------
        routes : list
            A list of route objects
        tours : list
            A list of tour objects
        """

        # Temporarily save the raw JSON objects for route definitions into a dictionary
        routes_raw = {}
        for r in routes:
            routes_raw[r["name"]] = r

        components = self.component_dictionary()

        for t in tours:
            new_tour = Tour(t["creation_time"], t["deletion_time"])
            for r in t["routes"]:
                new_route = Route()
                route_info = routes_raw[
                    r["name"]
                ]  # Look up the raw route info in dictionary
                # Number of route args objects supplied in tour must be equal to number of components in route
                if len(route_info["components"]) != len(r["args"]):
                    raise InputMismatchError(
                        f"{len(r['args'])} args object(s) are supplied for route {r['name']} "
                        f"in tour {t['name']} but route has {len(route_info['components'])} "
                        f"components. The number must match."
                    )
                for c, c_args in zip(route_info["components"], r["args"]):
                    if c_args is not None:
                        new_route.append(
                            components[f"{c['u']}-{c['v']}-{c['key']}"]["c"], **c_args
                        )
                    else:
                        new_route.append(
                            components[f"{c['u']}-{c['v']}-{c['key']}"]["c"]
                        )
                new_tour.append(new_route)
            self._tours[t["name"]] = new_tour

    def add_routes_and_tours_from_json_files(self, routes_filepath, tours_filepath):
        """Add a set of routes and tours from JSON files

        Parameters
        ----------
        routes_filepath : str
            The path to the routes JSON file
        tours_filepath : str
            The path to the tours JSON file
        """

        with open(routes_filepath, "r") as infile_r:
            routes = json.load(infile_r)

        with open(tours_filepath, "r") as infile_t:
            tours = json.load(infile_t)

        self.add_routes_and_tours_from_lists(routes, tours)

    def add_trains_from_list(self, trains):
        """Add trains to the model from a list of train objects

        Parameters
        ----------
        trains : list
            A list of train objects
        """

        for t in trains:
            self.add_train(
                t["name"], max_speed=t["max_speed"], tour=self._tours[t["tour"]]
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
