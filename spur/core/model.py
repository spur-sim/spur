"""Contains classes describing the model controller"""

import importlib
import logging
import json
import uuid
from typing import List, Dict

from simpy import Environment
from networkx import MultiGraph

from spur.core.train import Train
from spur.core.jitter import NoJitter
from spur.core.route import Route
from spur.core.tour import Tour
from spur.core.exception import (
    NotUniqueIDError,
    InputMismatchError,
    InvalidProjectDataError,
)

from spur.io.formats import read_components_json

# Set up the logging module for errors and debugging
logger = logging.getLogger(__name__)

# Whitelists of concrete class names that add_components() is allowed to
# resolve dynamically via importlib. Without this, any name importable
# into spur.core.component/jitter/collection's namespace would resolve -
# including abstract bases and unrelated helper classes pulled in via
# their own `from ... import ...` statements - not just the intended
# concrete types. When adding a new concrete Component/Jitter/Collection
# subclass, add its name here too.
_COMPONENT_TYPES = frozenset(
    {
        "TimedTrack",
        "MultiBlockTrack",
        "SimpleYard",
        "SimpleStation",
        "MultiTrackStation",
        "TimedStation",
        "SimpleCrossover",
    }
)
_JITTER_TYPES = frozenset(
    {
        "NoJitter",
        "UniformJitter",
        "GaussianJitter",
        "LognormalJitter",
        "DisruptionJitter",
    }
)
_COLLECTION_TYPES = frozenset({"BlockExclusiveZone"})


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

    def __init__(
        self,
        uid=None,
        sim_log_file=None,
        debug_log_file=None,
        agent_log_file=None,
        *args,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)
        # A unique identifier for this model instance, used to scope its
        # loggers so that no two Model instances ever share a logger (and
        # therefore never share/stack log handlers).
        self.uid = uid or uuid.uuid4().hex[:8]
        self.G = MultiGraph()
        self._trains = {}
        self._tours = {}  # Used as a container to keep track of possible tours
        self._collections = {}  # Used as a container to keep track of all collections

        # Verbatim copies of the input specs passed to add_components/
        # add_routes_and_tours/add_trains, retained so to_project_dictionary
        # can hand back an exact copy of the configuration used to build
        # this model.
        self._component_specs = []
        self._route_specs = []
        self._tour_specs = []
        self._train_specs = []

        # Set up logging environment for the simulation output, scoped to
        # this model instance so multiple Models never share a logger.
        self.simLog = logging.getLogger(f"sim.{self.uid}")
        self.simLog.setLevel(logging.INFO)

        # Set up stdout output and formatting - on by default since it's
        # scoped per-instance and can't stack across Model instances.
        sh = logging.StreamHandler()
        sh.setLevel(logging.INFO)
        sh.addFilter(SimLogFilter(self))
        simFormatter = logging.Formatter(
            "%(now)-6d %(name)-35s  %(message)s", style="%"
        )
        sh.setFormatter(simFormatter)
        self.simLog.addHandler(sh)

        # Logfile output is opt-in: pass a path to actually write a file.
        if sim_log_file is not None:
            fh = logging.FileHandler(sim_log_file, mode="w")
            fh.setLevel(logging.INFO)
            fh.addFilter(SimLogFilter(self))
            simFileFormatter = logging.Formatter(
                "%(now)-6d %(levelname)-8s %(name)-30s  %(message)s", style="%"
            )
            fh.setFormatter(simFileFormatter)
            self.simLog.addHandler(fh)

        if debug_log_file is not None:
            dfh = logging.FileHandler(debug_log_file, mode="w")
            dfh.setLevel(logging.DEBUG)
            dfh.addFilter(SimLogFilter(self))
            debugFileFormatter = logging.Formatter(
                "%(now)-6d %(levelname)-8s %(name)-30s  %(message)s", style="%"
            )
            dfh.setFormatter(debugFileFormatter)
            self.simLog.addHandler(dfh)

        # Set up the agent (train IN/OUT) log scope for this model instance.
        # Trains derive their own logger as a child of this one, so they
        # all share whichever handler is attached here without any two
        # Model instances ever touching the same logger.
        self.agentLog = logging.getLogger(f"agent.{self.uid}")
        self.agentLog.setLevel(logging.INFO)
        if agent_log_file is not None:
            afh = logging.FileHandler(agent_log_file, mode="w")
            afh.setLevel(logging.INFO)
            afh.addFilter(SimLogFilter(self))
            agentFormatter = logging.Formatter("%(now)d,%(name)s,%(message)s", style="%")
            afh.setFormatter(agentFormatter)
            self.agentLog.addHandler(afh)

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

    def _add_component(self, component_type, u, v, key, *args, **kwargs):
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
        model.add_components(project["components"])
        model.add_routes_and_tours(project["routes"], project["tours"])
        model.add_trains(project["trains"])
        return model

    def add_components(self, components: List[Dict]):
        """Add a list of components to the network

        Parameters
        ----------
        components : list
            The list of components to add
        """

        self._component_specs.extend(components)

        for c in components:
            if c["type"] not in _COMPONENT_TYPES:
                raise InvalidProjectDataError(
                    f"Unknown component type '{c['type']}'"
                )
            component = getattr(
                importlib.import_module("spur.core.component"), c["type"]
            )
            # Check jitter separately.
            if "jitter" in c.keys():
                if c["jitter"]["type"] not in _JITTER_TYPES:
                    raise InvalidProjectDataError(
                        f"Unknown jitter type '{c['jitter']['type']}'"
                    )
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
                    if c["collection"]["type"] not in _COLLECTION_TYPES:
                        raise InvalidProjectDataError(
                            f"Unknown collection type '{c['collection']['type']}'"
                        )
                    Collection = getattr(
                        importlib.import_module("spur.core.collection"),
                        c["collection"]["type"],
                    )
                    collection = Collection(model=self, uid=collection_id)
                    self.collections[collection_id] = collection
            else:
                collection = None

            self._add_component(
                component,
                c["u"],
                c["v"],
                c["key"],
                jitter=jitter,
                collection=collection,
                **c["args"],
            )

    def add_routes_and_tours(self, routes, tours):
        """Add routes and tours to the model from lists

        Parameters
        ----------
        routes : list
            A list of route objects
        tours : list
            A list of tour objects
        """

        self._route_specs.extend(routes)
        self._tour_specs.extend(tours)

        # Temporarily save the raw JSON objects for route definitions into a dictionary
        routes_raw = {}
        for r in routes:
            routes_raw[r["name"]] = r

        components = self.component_dictionary()

        for t in tours:
            new_tour = Tour(t["creation_time"], t["deletion_time"], name=t["name"])
            for r in t["routes"]:
                new_route = Route(name=r["name"])
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

    def add_trains(self, trains: List[Dict]) -> None:
        """Add trains to the model from a list of train objects

        Parameters
        ----------
        trains : list
            A list of train objects
        """

        self._train_specs.extend(trains)

        for t in trains:
            self.add_train(
                t["name"], max_speed=t["max_speed"], tour=self._tours[t["tour"]]
            )

    def to_project_dictionary(self) -> Dict:
        """Export this model's configuration as a project dictionary.

        This is the reverse of `from_project_dictionary`: it returns the
        exact components/routes/tours/trains specs this model was built
        from, so it can be saved, shared, or used to build a new model via
        `from_project_dictionary`. It does not capture live mid-run state
        (train positions, resource occupancy, or the simulation clock) -
        only models built through `add_components`/`add_routes_and_tours`/
        `add_trains` (including via `from_project_dictionary`) have
        anything to export; a model built by calling lower-level methods
        directly will export empty lists.

        Returns
        -------
        dict
            A dictionary with "components", "routes", "tours", and "trains"
            keys, in the same shape `from_project_dictionary` expects.
        """
        return {
            "components": list(self._component_specs),
            "routes": list(self._route_specs),
            "tours": list(self._tour_specs),
            "trains": list(self._train_specs),
        }
