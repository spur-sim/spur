import networkx as nx
from simpy.core import Environment

from .agent import Train


class Model(nx.MultiDiGraph, Environment):
    def __init__(self):
        super().__init__()
        self.train = Train()

    def print_train(self):
        print(self.train)
        print(type(self.train))

    def add_edge(self, u_for_edge, v_for_edge, key, **attr):
        print("WHATEVER")
        return super().add_edge(u_for_edge, v_for_edge, key=key, **attr)
