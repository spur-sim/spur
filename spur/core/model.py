import logging

from simpy import Environment
from networkx import MultiDiGraph

from spur.core.train import Train


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
        self.G = MultiDiGraph()
        self._trains = {}

        # Set up logging environment for the simulation output
        self.simLog = logging.getLogger("sim")
        self.simLog.setLevel(logging.INFO)

        # Set up stout output and formatting
        sh = logging.StreamHandler()
        sh.setLevel(logging.INFO)
        sh.addFilter(SimLogFilter(self))
        simFormatter = logging.Formatter(
            "%(now)-5d %(name)-25s  %(message)s", style="%"
        )
        sh.setFormatter(simFormatter)
        self.simLog.addHandler(sh)

        logger.info("Model setup complete!")

    @property
    def trains(self):
        return self._trains

    def add_component(self, component_type, u, v, key):
        # Initialize a brand new component of the type passed
        c = component_type(self, f"{u}-{v}-{key}")
        # Add it to the graph
        self.G.add_edge(u, v, key=key, c=c)
        return c

    def add_train(
        self, uid, u, v, key, max_speed, route=[], status=Train.STATUS_STOPPED
    ) -> Train:
        # Initialize a brand new train
        t = Train(self, uid, route, max_speed, status)
        # Add it to our dictionary of trains
        self.trains[uid] = t
        return t

    def start(self):
        # We go through each train and get it started
        self.simLog.info("Simulation is starting...")
        for key in self.trains.keys():
            self._trains[key].start()
