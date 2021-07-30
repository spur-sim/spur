from simpy import Interrupt

from spur.core.base import Agent


class Train(Agent):
    __name__ = "Train"

    def __init__(
        self, model, uid, route, max_speed, status=Agent.STATUS_STOPPED
    ) -> None:
        self._status = status
        super().__init__(model, uid, route, max_speed, status)

    def run(self):
        """The action method of the train agent.

        Train agents run a simple and continuous process of moving through their
        prescribed route, alternately requesting access to a component and then
        calling the `_do()` method of the component to be processed. Agents can
        be interrupted from their current process and assigned a new route
        before they start running again.
        """
        if self.current_component is None:
            print(
                f"[{self._model.now}:{self.uid}] No current component found, starting run"
            )
        for idx, component in enumerate(self.route):
            print(f"[{self._model.now}:{self.uid}] Requesting use of {component.uid}")

            # Ask to access the first component in the list
            with component.resource.request() as req:
                yield req

                # We're in. Let's update our own information
                # Release the train from the current component
                if self.current_component is not None:
                    self.current_component.release_train(self)

                component.accept_train(self)
                self.current_component = component

                print(
                    f"[{self._model.now}:{self.uid}] Access to {self.current_component._uid} granted, rolling now"
                )
                # Now we get the component to shepherd us through
                try:
                    yield self._model.process(self.current_component._do(self))
                except Interrupt:
                    print(f"[{self._model.now}] {self._uid} was interrupted")

                # Finished traversing
                print(
                    f"[{self._model.now}:{self.uid}] Finished traversing {self.current_component.uid}"
                )
