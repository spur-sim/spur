import random
import logging

from abc import ABC, abstractmethod

from scipy.stats import norm

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
    def __init__(self, minimum, maximum) -> None:
        self._min = minimum
        self._max = maximum
        super().__init__()

    def jitter(self):
        return random.randint(self._min, self._max)


class GaussianJitter(BaseJitter):
    def __init__(self, mean=0, std=1) -> None:
        self._mean = mean
        self._std = std
        super().__init__()

    def jitter(self):
        return round(norm.rvs(loc=self._mean, scale=self._std))


class DisruptionJitter(BaseJitter):
    def __init__(self, p, delay) -> None:
        self._p = p
        self._delay = int(delay)
        super().__init__()

    def jitter(self):
        if random.random() < self._p:
            return self._delay
        else:
            return 0
