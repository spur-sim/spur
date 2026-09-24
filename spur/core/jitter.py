"""Contains classes describing random perturbations known as jitter"""

import logging

from abc import ABC, abstractmethod

from scipy.stats import norm, lognorm
import numpy as np

from spur.core.exception import NotAProbabilityError

logger = logging.getLogger(__name__)


class BaseJitter(ABC):
    """Abstract jitter component for perturbations

    Attributes
    ----------
    rng : `numpy.random.Generator`
        The random number generator all draws are taken from. A component
        binds its model's generator here when the jitter is attached to it,
        so seeding a `Model` makes its jitter reproducible. A jitter used
        outside of any model gets its own unseeded generator.

    Methods
    -------
    jitter()
        Returns a perturbation value
    """

    __name__ = "BaseComponent"

    _rng = None

    def __init__(self) -> None:
        super().__init__()

    @property
    def rng(self) -> np.random.Generator:
        if self._rng is None:
            self._rng = np.random.default_rng()
        return self._rng

    @rng.setter
    def rng(self, rng: np.random.Generator) -> None:
        self._rng = rng

    @abstractmethod
    def jitter(self):
        """Produce a perturbation

        The value produced is dependent on the type of Jitter
        class used, and the parameters supplied.

        Returns
        -------
        int
            The perturbation value, in model time steps.
        """
        pass


class NoJitter(BaseJitter):
    """Jitter component that produces no jitter

    NoJitter is used as a default non-perturbation setting for many
    components.

    Methods
    -------
    jitter()
        Returns a zero perturbation value
    """

    __name__ = "NoJitter"

    def __init__(self) -> None:
        super().__init__()

    def jitter(self):
        return 0


class UniformJitter(BaseJitter):
    """Jitter component that produces uniformly distributed perturbations

    Methods
    -------
    jitter()
        Calculates and returns a uniformly distributed perturbation value
    """

    __name__ = "UniformJitter"

    def __init__(self, minimum: int, maximum: int) -> None:
        """
        Parameters
        ----------
        minimum : int
            The lower bound of the uniform distribution
        maximum : int
            The upper bound of the uniform distribution
        """
        if maximum < minimum:
            raise ValueError("Maximum value should be larger than minimum.")
        self._min = minimum
        self._max = maximum
        super().__init__()

    def jitter(self):
        return int(self.rng.integers(self._min, self._max + 1))


class GaussianJitter(BaseJitter):
    """Jitter component producing Gaussian (normally) distributed perturbations

    Methods
    -------
    jitter()
        Calculates and returns a Gaussian distributed perturbation value
    """

    __name__ = "GaussianJitter"

    def __init__(self, mean=0.0, std=1.0) -> None:
        """
        Parameters
        ----------
        mean : float, optional
            The mean value of the perturbation, by default 0.0
        std : float, optional
            The standard deviation of the perturbation, by default 1.0
        """

        self._mean = mean
        self._std = std
        super().__init__()

    def jitter(self) -> int:
        return round(norm.rvs(loc=self._mean, scale=self._std, random_state=self.rng))


class LognormalJitter(BaseJitter):
    """Jitter component producing lognormally distributed perturbations

    This perturbation assumes a supplied mean and standard deviation
    that is appropriate for the context. For example, a travel time component
    might supply the average and standard deivation of travel times as the
    parmaters for this jitter.

    Note that this component still returns a *perturbation*, meaning that output
    values sampled form the supplied distribution are shifted by the mean value
    so that the resulting jitter is centred on zero. This means you should also
    supply appropriate parameters (e.g. travel times) to the underlying
    component. One suggestion is to use the mean travel times there as well.

    Methods
    -------
    jitter()
        Calculates and returns a lognormally distributed perturbation value
    """

    def __init__(self, mean=10.0, std=1.0) -> None:
        """
        Parameters
        ----------
        mean : float, optional
            The mean value of the lognormal distribution, by default 0.0
        std : float, optional
            The standard deviation of the lognormal distribution, by default 1.0
        """

        # Calculate the s parameter used by scipy's lognorm function based
        # on the supplied mean and standard deviation.
        a = 1 + (std / mean) ** 2
        self._s = np.sqrt(np.log(a))
        self._scale = mean / np.sqrt(a)
        self._mean = mean
        super().__init__()

    def jitter(self):
        return round(
            lognorm.rvs(s=self._s, scale=self._scale, random_state=self.rng)
            - self._mean
        )


class DisruptionJitter(BaseJitter):
    """Jitter component producing perturbations based on probabilistic disruptions

    This Jitter checks a random number against a supplied probability valuee each
    each time `jitter()` is called. If the value is below the probability threshold,
    a specified perturbation is returned. Otherwise, no perturbation occurs.

    Methods
    -------
    jitter()
        Calculates and returns a perturbation value

    Raises
    ------
    NotAProbabilityError
        If the supplied probability is not between [0, 1]
    """

    def __init__(self, p: float, delay: int) -> None:
        """
        Parameters
        ----------
        p : float
            A value between 0 and 1
        delay : int
            The perturbation to return if the disruption is triggered.
        """

        if p > 1.0 or p < 0.0:
            raise NotAProbabilityError(
                "The probability value must be in the range [0, 1]"
            )
        self._p = p
        self._delay = int(delay)
        super().__init__()

    def jitter(self):
        if self.rng.random() < self._p:
            return self._delay
        else:
            return 0
