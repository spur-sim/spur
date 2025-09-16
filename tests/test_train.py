from spur.core.train import Train


def test_initialization(toy_model_base, toy_model_tour):
    t = Train(toy_model_base, "T-1", toy_model_tour, 50)
    assert t.uid == "T-1"
    assert t.speed == 0
    assert repr(t) == "Train T-1"


def test_set_speed(toy_model_base, toy_model_tour):
    t = Train(toy_model_base, "T-1", toy_model_tour, 50)
    assert t.speed == 0
    t.speed = 10
    assert t.speed == 10
