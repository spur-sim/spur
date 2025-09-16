from spur.core.collection import BlockExclusiveZone
from spur.core.component import TimedTrack


class TestBlockExclusiveZone:
    def test_block_exclusive_zone_creation(self, toy_model_base):
        toy_model_base.add_component(
            TimedTrack, "1", "2", "A", traversal_time=180, capacity=1, collection="test"
        )
        toy_model_base.add_component(
            TimedTrack, "2", "3", "A", traversal_time=80, capacity=2, collection="test"
        )
        toy_model_base.add_component(
            TimedTrack, "3", "4", "A", traversal_time=80, capacity=1, collection="test"
        )
