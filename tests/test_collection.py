from spur.core.collection import BlockExclusiveZone
from spur.core.component import TimedTrack
from spur.core.train import Train


class TestBlockExclusiveZone:
    def test_initialization(self, toy_model_base):
        toy_model_base._add_component(
            TimedTrack, "1", "2", "A", traversal_time=180, capacity=1, collection="test"
        )
        toy_model_base._add_component(
            TimedTrack, "2", "3", "A", traversal_time=80, capacity=2, collection="test"
        )
        toy_model_base._add_component(
            TimedTrack, "3", "4", "A", traversal_time=80, capacity=1, collection="test"
        )
        bez = BlockExclusiveZone(toy_model_base, "B-1")

    def test_wait_queue(self, toy_model_base, toy_model_tour):
        toy_model_base._add_component(
            TimedTrack, "1", "2", "A", traversal_time=180, capacity=1, collection="test"
        )
        toy_model_base._add_component(
            TimedTrack, "2", "3", "A", traversal_time=80, capacity=2, collection="test"
        )
        toy_model_base._add_component(
            TimedTrack, "3", "4", "A", traversal_time=80, capacity=1, collection="test"
        )
        bez = BlockExclusiveZone(toy_model_base, "B-1")
        t1 = Train(toy_model_base, "T-1", toy_model_tour, 50)
        assert bez.can_accept_agent(t1) == True
        bez.accept_agent(t1)
        t2 = Train(toy_model_base, "T-2", toy_model_tour, 50)
        assert bez.can_accept_agent(t2) == False
