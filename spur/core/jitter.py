import random
import logging

from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)


class BaseJitter(ABC):
    def __init__(self) -> None:
        super().__init__()

    @abstractmethod
    def jitter(self):
        pass


class NoJitter(BaseJitter):
    def __init__(self) -> None:
        super().__init__()

    def jitter(self):
        return 0


class UniformJitter(BaseJitter):
    def __init__(self, min, max) -> None:
        self._min = min
        self._max = max
        super().__init__()

    def jitter(self):
        return random.randint(self._min, self._max)
