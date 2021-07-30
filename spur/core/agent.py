from simpy import Interrupt


class BaseAgent:
    __name__ = "Base Agent Type"

    def __init__(self, model, uid) -> None:
        self._model = model
        self._uid = uid
        self._component = None
        self._route = []

    def start(self):
        self.action = self._model.process(self.run())

    def run(self):
        if self._component is None:
            raise NotImplementedError
        raise NotImplementedError

    @property
    def component(self):
        return self._component

    @component.setter
    def component(self, c):
        self._component = c

    @property
    def route(self):
        return self._route

    @route.setter
    def route(self, route):
        self._route = route


class Train(BaseAgent):
    __name__ = "Train"

    def __init__(self, model, key) -> None:
        super().__init__(model, key)

    def run(self):
        while True:
            print(
                f"[{self._model.now}] Requesting use of component {self.component._uid}"
            )
            with self._component.resource.request() as req:
                yield req

                print(
                    f"[{self._model.now}] Access to {self.component._uid} granted, rolling now"
                )
                try:
                    yield self._model.process(self._component._do(self))
                except Interrupt:
                    print(f"[{self._model.now}] {self._uid} was interrupted")

                # Now we get the next component


# class Train:
#     __name__ = "Train"

#     def __init__(self, model, component):
#         self.model = model

#         # The component the train is currently attached to
#         self.component = component
#         self.component.add_train(self)

#         # The current action that the train is trying to do
#         self.action = model.process(self.move())

#     def run(self):
#         print("Starting to roll at", self.model.now)
#         roll_duration = 5
#         yield self.model.process(self.move(roll_duration))

#         print("Start rolling at", self.model.now)
#         trip_duration = 2
#         yield self.model.timeout(trip_duration)

#     def move(self):
#         with self.component.request() as request:
#             yield request

#             print(f"Train enters component {self.component.key} at {self.model.now}")

#             yield self.model.process(self.component.traverse(self.model))

#             print(f"Finished with cpnt {self.component.key} at {self.model.now}")
