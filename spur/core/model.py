from simpy import Environment
from networkx import MultiDiGraph

from spur.core.agent import Train


class Model(Environment):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.G = MultiDiGraph()
        self._trains = {}

    @property
    def trains(self):
        return self._trains

    def add_component(self, component_type, u, v, key):
        # Initialize a brand new component of the type passed
        c = component_type(self, f"{u}-{v}-{key}")
        # Add it to the graph
        self.G.add_edge(u, v, key=key, c=c)
        return c

    def add_train(self, uid, u, v, key, route=[]) -> Train:
        # Initialize a brand new train
        t = Train(self, uid, route)
        # Add it to our dictionary of trains
        self.trains[uid] = t
        return t

    def start(self):
        # We go through each train and get it started
        for key in self.trains.keys():
            self._trains[key].start()
