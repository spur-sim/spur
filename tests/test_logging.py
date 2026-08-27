import logging

from spur.core import Model
from spur.core.component import TimedTrack
from spur.core.route import Route
from spur.core.tour import Tour


def _build_model(agent_log_file=None, sim_log_file=None):
    m = Model(agent_log_file=agent_log_file, sim_log_file=sim_log_file)
    m._add_component(TimedTrack, "1", "2", "A", traversal_time=5, capacity=1)
    m._add_component(TimedTrack, "2", "3", "A", traversal_time=5, capacity=1)
    r = Route()
    for c in m.components:
        r.append(c)
    t = Tour(creation_time=0, deletion_time=100)
    t.append(r)
    m.add_train("train-1", max_speed=10, tour=t)
    return m


def test_models_do_not_share_agent_or_sim_loggers(tmp_path):
    """Two Model instances must never share a logger or its handlers."""
    agent_log_a = tmp_path / "agent_a.log"
    agent_log_b = tmp_path / "agent_b.log"
    sim_log_a = tmp_path / "sim_a.log"
    sim_log_b = tmp_path / "sim_b.log"

    model_a = _build_model(str(agent_log_a), str(sim_log_a))
    model_a.start()
    model_a.run(until=20)

    model_b = _build_model(str(agent_log_b), str(sim_log_b))
    model_b.start()
    model_b.run(until=20)

    assert model_a.agentLog.name != model_b.agentLog.name
    assert model_a.simLog.name != model_b.simLog.name

    # Each model attached exactly one file handler to its own logger - no
    # stacking, no cross-instance sharing.
    assert len(model_a.agentLog.handlers) == 1
    assert len(model_b.agentLog.handlers) == 1

    # The old global "agent"/"sim" loggers must never receive a handler.
    assert logging.getLogger("agent").handlers == []
    assert logging.getLogger("sim").handlers == []

    text_a = agent_log_a.read_text()
    text_b = agent_log_b.read_text()

    assert "train-1" in text_a
    assert "train-1" in text_b
    # Neither file was truncated or duplicated by the other model's run.
    assert text_a.count("IN,") == text_b.count("IN,") == 2
    assert text_a.count("OUT,") == text_b.count("OUT,") == 2


def test_model_without_log_files_writes_nothing(tmp_path, monkeypatch):
    """With no *_log_file args, no files or directories are created."""
    monkeypatch.chdir(tmp_path)
    m = _build_model()
    m.start()
    m.run(until=20)

    assert not (tmp_path / "log").exists()
    assert m.agentLog.handlers == []
