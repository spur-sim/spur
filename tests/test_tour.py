from spur.core.route import Route
from spur.core.tour import Tour, TourSegment


def test_tour_append(toy_model_with_components):
    t = Tour(creation_time=10, deletion_time=100)
    r = Route()
    for c in toy_model_with_components.components:
        r.append(c)

    r = Route()
    for c in toy_model_with_components.components[::-1]:
        r.append(c)
    t.append(r)
