"""
Base classes of Spur's component types.

:class:`BaseComponent` defines the abstract base component.
"""
import logging
from abc import ABC, abstractmethod

from simpy.resources.resource import Resource
from simpy.resources.store import Store

logger = logging.getLogger(__name__)


class StatusException(Exception):
    pass


class SimLogFilter(logging.Filter):
    def __init__(self, model, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.model = model

    def filter(self, record) -> bool:
        record.now = self.model.now
        record.name = record.name.split(".")[-1]
        return True


class BaseItem(ABC):
    __name__ = "Base Item"

    def __init__(self, model, uid) -> None:
        self._model = model
        self.uid = uid

        # Set base logging information
        self.logger = logging.getLogger(f"{logger.name}.{uid}")
        # Set simulation logging information
        self.simLog = logging.getLogger("sim.base")
        self.simLog.debug("I am alive!")

    @property
    def model(self):
        return self._model

    @property
    def uid(self):
        return self._uid

    @uid.setter
    def uid(self, uid):
        self._uid = uid


class BaseComponent(BaseItem, ABC):
    """The base component class used for the model.

    A component represents a physical piece of infrastructure that an agent
    (e.g. a train) moves through. Every component must have a `do()` method
    implemented that the agent interacts with.

    :raises NotImplementedError: Methods that should be implemented but are not
    raise an error.
    """

    __name__ = "BaseComponent"

    def __init__(self, model, uid, jitter) -> None:
        self._agents = {}
        self._jitter = jitter
        super().__init__(model, uid)

    def __repr__(self):
        return f"Component {self.uid}"

    def accept_agent(self, agent):
        self._agents[agent.uid] = agent
        self.simLog.debug(f"Accepted agent {agent.uid}")
        self.simLog.debug(f"Current Agents (after accept): {self._agents}")

    def release_agent(self, agent):
        self.simLog.debug(f"Releasing agent {agent.uid}")
        self.simLog.debug(f"Current Agents (before release): {self._agents}")
        return self._agents.pop(agent.uid)

    def as_dict(self):
        d = self.__dict__
        d.pop("_res", None)
        d.pop("_agents", None)
        d.pop("simLog", None)
        d.pop("logger", None)
        d.pop('_model', None)
        # Now build a dictionary with what's left
        clean = {
            'type': self.__name__,
            'uid': d['_uid'],
            'jitter': d['_jitter'].__name__,
        }
        mandatory_keys = ['uid', 'jitter']
        for k in d.keys():
            clean_k = k.lstrip('_')
            if clean_k not in mandatory_keys:
                if "args" not in clean.keys():
                    clean['args'] = {clean_k: d[k]}
                else:
                    clean['args'][clean_k] = d[k]
        return clean

    @abstractmethod
    def do(self, *args, **kwargs):
        pass


class ResourceComponent(BaseComponent):
    __name__ = "Base Resource Component"

    def __init__(self, model, uid, resource: Resource, jitter) -> None:
        self._res = resource
        super().__init__(model, uid, jitter)

    @property
    def resource(self):
        return self._res


class StoreComponent(BaseComponent):
    __name__ = "Store Component"

    def __init__(self, model, uid, store: Store) -> None:
        self._store = store
        super().__init__(model, uid)


class Agent(BaseItem, ABC):
    __name__ = "Agent"

    def __init__(self, model, uid, route, max_speed) -> None:
        self._current_segment = None  # The current segment
        self.route = route
        self.speed = 0
        self.max_speed = max_speed
        super().__init__(model, uid)
        self.agentLog = logging.getLogger("agent")
        self.agentLog.setLevel(logging.INFO)
        # Set up logfile output for agents
        fh = logging.FileHandler("log/agent.log", mode="w")
        fh.setLevel(logging.INFO)
        fh.addFilter(SimLogFilter(model))
        simFileFormatter = logging.Formatter("%(now)d,%(name)s,%(message)s", style="%")
        fh.setFormatter(simFileFormatter)
        self.agentLog.addHandler(fh)

    @property
    def speed(self):
        return self._speed

    @speed.setter
    def speed(self, speed):
        if speed < 0:
            raise ValueError("Speed must be non-negative")
        self._speed = speed

    @property
    def max_speed(self):
        return self._max_speed

    @max_speed.setter
    def max_speed(self, max_speed):
        if max_speed <= 0:
            raise ValueError("Maximum speed must be positive")
        self._max_speed = max_speed

    @property
    def route(self):
        return self._route

    @route.setter
    def route(self, route):
        self._route = route

    def transfer_to(self, segment):
        # First we tell the previous component we're done
        if self._current_segment:
            self._current_segment.component.release_agent(self)
        # Then we tell the next component we're here
        self._current_segment = segment
        self._current_segment.component.accept_agent(self)

    def start(self):
        self.simLog.debug("Started!")
        self.action = self.model.process(self.run())

    @abstractmethod
    def run(self):
        pass


if __name__ == "__main__":
    pass
