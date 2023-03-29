"""
Base classes of Spur's component types.

:class:`BaseComponent` defines the abstract base component.
"""
import logging
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, List

from simpy.core import BoundClass, Environment
from simpy.resources.resource import Resource, Request, Release
from simpy.resources.store import Store

from spur.core.exception import NotPositiveError, NotUniqueIDError

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
    """Abstract base item class for components and agents

    This abstract base class is inhereted by all other simulation objects and
    should not be used directly.

    Attributes
    ----------
    uid : mixed
        A unique identifier for a given item.
    logger : `logging.logger`
    """

    __name__ = "Base Item"

    def __init__(self, model, uid) -> None:
        self._model = model
        if self._model._uid_unique(uid) == False:
            raise NotUniqueIDError(f"UID {uid} has been used already.")
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

    Raises
    ------
    NotImplementedError
        If there are methods that should be overriden and implemented but are not.
    """

    __name__ = "BaseComponent"

    def __init__(self, model, uid, jitter) -> None:
        self._agents = {}
        self._jitter = jitter
        super().__init__(model, uid)

    def __repr__(self):
        return f"Component {self.uid}"

    def accept_agent(self, agent):
        """Accept a request for an agent to use the component

        Parameters
        ----------
        agent : Any child of `BaseAgent` class
            The agent that is requesting use of the component.
        """

        self._agents[agent.uid] = agent
        self.simLog.debug(f"Accepted agent {agent.uid}")
        self.simLog.debug(f"Current Agents (after accept): {self._agents}")

    def release_agent(self, agent):
        """Release an agent from the component resource

        Parameters
        ----------
        agent : Any child of `BaseAgent` class
            The agent that is being released from this component

        Returns
        -------
        `BaseAgent` child
            The agent that has been released from this component.
        """

        self.simLog.debug(f"Releasing agent {agent.uid}")
        self.simLog.debug(f"Current Agents (before release): {self._agents}")
        return self._agents.pop(agent.uid)

    def as_dict(self):
        """Return a dictionary describing the attributes of the component

        Returns
        -------
        dict
            A dictionary contianing the required keys and values describing the component.
        """

        d = self.__dict__
        d.pop("_res", None)
        d.pop("_agents", None)
        d.pop("simLog", None)
        d.pop("logger", None)
        d.pop("_model", None)
        # Now build a dictionary with what's left
        clean = {
            "type": self.__name__,
            "uid": d["_uid"],
            "jitter": d["_jitter"].__name__,
        }
        mandatory_keys = ["uid", "jitter"]
        for k in d.keys():
            clean_k = k.lstrip("_")
            if clean_k not in mandatory_keys:
                if "args" not in clean.keys():
                    clean["args"] = {clean_k: d[k]}
                else:
                    clean["args"][clean_k] = d[k]
        return clean

    def check_usage_eligibility(self, agent: 'Agent'):
        """Check whether `agent` is eligible to use this component based on component state.

        Always returns True by default, meaning the decision to accept the agent's
        request is purely based on resource capacity. Can be overriden in child classes to
        include custom logic.

        Parameters
        ----------
        agent : Any child of `Agent` class
            The agent that is requesting use of the component.

        Returns
        -------
        bool
            Whether `agent` is eligible to use the component.
        """

        return True

    @abstractmethod
    def do(self, *args, **kwargs):
        raise NotImplementedError("The do method for this object must be overwritten")


class ResourceComponent(BaseComponent):
    __name__ = "Base Resource Component"

    def __init__(self, model, uid, resource: 'SpurResource', jitter) -> None:
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


class SpurRequest(Request):
    """A custom class that inherits SimPy's Request class.

    This class also stores the agent making the request as a property.

    Attributes
    ----------
    agent : Any child of `Agent` class
        The agent making the request
    """

    def __init__(self, resource: 'SpurResource', agent: 'Agent'):
        self._agent = agent
        super().__init__(resource)

    @property
    def agent(self):
        return self._agent


class SpurResource(Resource):
    """A custom class that inherits SimPy's Resource class.

    This overrides the _do_put() method in the parent class to include a check
    with the linked component regarding whether an agent could use the resource,
    in addition to deciding based on the resource capacity.

    Attributes
    ----------
    component : Any child of `ResourceComponent` class
        The associated component for the resource
    """

    users: List[SpurRequest]

    def __init__(self, env: Environment, component: ResourceComponent, capacity: int = 1):
        self._component = component
        super().__init__(env, capacity)

    if TYPE_CHECKING:

        def request(self, agent: 'Agent' = None) -> SpurRequest:
            """Request a usage slot for the given *agent*."""
            return SpurRequest(self, agent)

        def release(self, request: SpurRequest) -> Release:
            """Release a usage slot."""
            return Release(self, request)

    else:
        request = BoundClass(SpurRequest)
        release = BoundClass(Release)

    def _do_put(self, event: SpurRequest) -> None:
        if (
            len(self.users) < self.capacity
            and self._component.check_usage_eligibility(event.agent)
        ):
            self.users.append(event)
            event.usage_since = self._env.now
            event.succeed()

    def process_queue(self) -> None:
        """Explicitly trigger the processing of the wait queue of trains wanting to use the resource,
        instead of only triggering upon a new request or a train releasing the resource.

        Returns
        -------
        None
        """

        self._trigger_put(None)


class Agent(BaseItem, ABC):
    __name__ = "Agent"

    def __init__(self, model, uid, tour, max_speed) -> None:
        self._current_segment = None  # The current segment
        self.tour = tour
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
            raise NotPositiveError("Speed must be non-negative")
        self._speed = speed

    @property
    def max_speed(self):
        return self._max_speed

    @max_speed.setter
    def max_speed(self, max_speed):
        if max_speed <= 0:
            raise NotPositiveError("Maximum speed must be positive")
        self._max_speed = max_speed

    @property
    def tour(self):
        return self._tour

    @tour.setter
    def tour(self, tour):
        self._tour = tour

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
