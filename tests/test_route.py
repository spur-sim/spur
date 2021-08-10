from spur.core.route import Route


def test_route_append(toy_model_with_components):
    r = Route()
    for c in toy_model_with_components.components:
        r.append(c)
    assert [s.component.uid for s in r.traverse()] == [
        c.uid for c in toy_model_with_components.components
    ]


def test_route_insert(toy_model_with_components):
    r = Route()
    r.append(toy_model_with_components.components[0])
    r.append(toy_model_with_components.components[1])
    r.insert(toy_model_with_components.components[2], 1)
    assert [s.component.uid for s in r.traverse()] == [
        toy_model_with_components.components[0].uid,
        toy_model_with_components.components[2].uid,
        toy_model_with_components.components[1].uid,
    ]
