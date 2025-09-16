from spur.core.route import Route
from spur.core.tour import Tour, TourSegment


class TestTourInitialization:
    def test_tour_append(self, toy_model_with_components):
        t = Tour(creation_time=10, deletion_time=100)
        r1 = Route()
        for c in toy_model_with_components.components:
            r1.append(c)

        r2 = Route()
        for c in toy_model_with_components.components[::-1]:
            r2.append(c)
        t.append(r1)
        assert len(t.tour_segments) == 1
        t.append(r2)
        assert len(t.tour_segments) == 2

    def test_tour_insert(self, toy_model_with_components):
        t = Tour(creation_time=10, deletion_time=100)
        r1 = Route()
        for c in toy_model_with_components.components:
            r1.append(c)

        r2 = Route()
        for c in toy_model_with_components.components[::-1]:
            r2.append(c)
        t.insert(r2, 0)
        assert len(t.tour_segments) == 1
        t.insert(r1, 0)
        assert len(t.tour_segments) == 2
