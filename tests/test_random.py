import random

import numpy as np
import pytest

from spur.core import Model
from spur.core.component import MultiTrackStation, TimedTrack
from spur.core.jitter import (
    DisruptionJitter,
    GaussianJitter,
    LognormalJitter,
    UniformJitter,
)
from spur.io.formats import (
    read_components_json,
    read_routes_json,
    read_tours_json,
    read_trains_json,
)

JITTERS = [
    lambda: UniformJitter(0, 100),
    lambda: GaussianJitter(mean=0, std=50),
    lambda: LognormalJitter(mean=100, std=40),
    lambda: DisruptionJitter(p=0.5, delay=300),
]


def _draws(seed, make_jitter, n=50):
    model = Model(seed=seed)
    component = TimedTrack(model, "C-1", 100, jitter=make_jitter())
    return [component.jitter.jitter() for _ in range(n)]


def _project(components_json_file, routes_json_file, tours_json_file, trains_json_file):
    return {
        "components": read_components_json(components_json_file),
        "routes": read_routes_json(routes_json_file),
        "tours": read_tours_json(tours_json_file),
        "trains": read_trains_json(trains_json_file),
    }


def _events(project, seed, until=36900):
    model = Model.from_project_dictionary(project, seed=seed)
    model.start()
    model.run(until=until)
    model.log_current_state()
    return [e.model_dump() for e in model.events]


class TestSeededJitter:
    @pytest.mark.parametrize("make_jitter", JITTERS)
    def test_same_seed_gives_same_draws(self, make_jitter):
        assert _draws(42, make_jitter) == _draws(42, make_jitter)

    @pytest.mark.parametrize("make_jitter", JITTERS)
    def test_different_seeds_give_different_draws(self, make_jitter):
        assert _draws(1, make_jitter) != _draws(2, make_jitter)

    def test_uniform_jitter_bounds_are_inclusive(self):
        assert set(_draws(0, lambda: UniformJitter(0, 2), n=500)) == {0, 1, 2}

    def test_jitter_outside_a_model_still_works(self):
        values = {UniformJitter(1, 3).jitter() for _ in range(200)}
        assert values <= {1, 2, 3}

    def test_assigning_a_jitter_binds_the_models_generator(self):
        model = Model(seed=5)
        component = TimedTrack(model, "C-1", 100)
        component.jitter = UniformJitter(0, 10)
        assert component.jitter.rng is model.rng


class TestSeededComponents:
    @staticmethod
    def _dwell(seed):
        model = Model(seed=seed)
        station = MultiTrackStation(model, "S-1", 1, 1, 30, 10.0, 1.5, 0.0, 60.0)
        station._train_is_stopping = lambda train, current: True
        model.process(station.do(None))
        model.run()
        return model.now

    def test_multitrack_station_dwell_is_reproducible(self):
        assert self._dwell(3) == self._dwell(3)

    def test_multitrack_station_dwell_varies_with_seed(self):
        assert len({self._dwell(s) for s in range(10)}) > 1


class TestSeededModel:
    def test_seed_defaults_to_none_and_is_stored(self):
        assert Model().seed is None
        assert Model(seed=7).seed == 7

    def test_unseeded_models_draw_differently(self):
        assert Model().rng.random() != Model().rng.random()

    def test_same_seed_reproduces_a_full_run(
        self, components_json_file, routes_json_file, tours_json_file, trains_json_file
    ):
        project = _project(
            components_json_file, routes_json_file, tours_json_file, trains_json_file
        )
        assert _events(project, seed=7) == _events(project, seed=7)

    def test_different_seeds_change_a_full_run(
        self, components_json_file, routes_json_file, tours_json_file, trains_json_file
    ):
        project = _project(
            components_json_file, routes_json_file, tours_json_file, trains_json_file
        )
        assert _events(project, seed=7) != _events(project, seed=8)

    def test_seeded_run_does_not_touch_global_random_state(
        self, components_json_file, routes_json_file, tours_json_file, trains_json_file
    ):
        project = _project(
            components_json_file, routes_json_file, tours_json_file, trains_json_file
        )
        py_state = random.getstate()
        np_state = np.random.get_state()

        _events(project, seed=7)

        assert random.getstate() == py_state
        after = np.random.get_state()
        assert after[0] == np_state[0]
        assert np.array_equal(after[1], np_state[1])
        assert after[2:] == np_state[2:]

    def test_models_in_one_process_do_not_interfere(
        self, components_json_file, routes_json_file, tours_json_file, trains_json_file
    ):
        project = _project(
            components_json_file, routes_json_file, tours_json_file, trains_json_file
        )
        alone = _events(project, seed=1)

        a = Model.from_project_dictionary(project, seed=1)
        b = Model.from_project_dictionary(project, seed=2)
        a.start()
        b.start()
        for t in [*range(3600, 36900, 3600), 36900]:
            a.run(until=t)
            b.run(until=t)
        a.log_current_state()

        assert [e.model_dump() for e in a.events] == alone
