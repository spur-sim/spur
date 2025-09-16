import pytest


from spur.core.jitter import NoJitter, UniformJitter


class TestNoJitter:
    def test_initialization(self):
        j = NoJitter()

    def test_jitter(self):
        j = NoJitter()
        assert j.jitter() == 0


class TestUniformJitter:
    def test_initialization(self):
        j = UniformJitter(5, 10)

    @pytest.mark.parametrize(
        ("min_val", "max_val"),
        [(10, 5)],
    )
    def test_initialization_with_invalid_inputs(self, min_val, max_val):
        with pytest.raises(ValueError):
            j = UniformJitter(min_val, max_val)

    def test_jitter(self):
        j = UniformJitter(5, 10)
        v = [j.jitter() for x in range(100)]
        for val in v:
            assert val >= 5 and val <= 10
