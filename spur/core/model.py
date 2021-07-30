from simpy import Environment
from networkx import MultiDiGraph

from spur.core.agent import Train


class Model(Environment):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.G = MultiDiGraph()
        self._trains = {}

    def add_component(self, component_type, u, v, key):
        # Initialize a brand new component of the type passed
        c = component_type(self, f"{u}-{v}-{key}")
        # Add it to the graph
        self.G.add_edge(u, v, key=key, c=c)
        return c

    def add_train(self, uid, u, v, key) -> Train:
        # Initialize a brand new train
        t = Train(self, uid)
        # Add train to component and model
        self.G[u][v][key]["c"]._add_train(t)
        self._trains[uid] = t
        # Attach component to train
        t.component = self.G[u][v][key]["c"]
        return t

    def start(self):
        # We go through each train and get it started
        for key in self._trains.keys():
            self._trains[key].start()
