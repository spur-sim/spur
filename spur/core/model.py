from simpy import Environment

from .agent import Train


class Model(Environment):
    def __init__(self):
        super().__init__()
        self.trains = {}
        self.components = {}

    def print_train(self):
        print(self.train)
        print(type(self.train))

    def add_train(self, key, component):
        self.trains[key] = Train(self, component)
        component.add_train(self.trains[key])

    def add_component(self, key, component):
        self.components[key] = component
