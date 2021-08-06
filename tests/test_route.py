from spur.core.route import Route, RouteSegment


def test_route_iterator(toy_model_with_components):
    r = Route()
    for c in toy_model_with_components.components:
        r.append_segment(c)
        r.append_segment(c)
    assert isinstance(next(r), RouteSegment)
