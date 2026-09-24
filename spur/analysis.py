"""Turn a run's structured events into dwell, headway and delay metrics.

`analyze` is a pure function over the events a `Model` emitted (see
`spur.core.event`) and the project they were run from, so it works equally on
a live `Model.events` list and on events that were stored and read back later.
See the "Analysing a run" guide for the exact definitions.
"""

from collections import defaultdict
from statistics import mean, stdev
from typing import Dict, List, Optional, Sequence, Tuple

from pydantic import BaseModel

from spur.core.event import SimEvent, SimEventType
from spur.core.exception import InputMismatchError

DEFAULT_ON_TIME_THRESHOLD = 120

# (component uid, scheduled arrival, scheduled departure)
_Segment = Tuple[str, Optional[int], Optional[int]]


class Stats(BaseModel):
    """Summary statistics. Fields are None when they can't be computed: everything
    but `n` when there are no values, and `std` (sample standard deviation) when
    there is only one."""

    n: int
    mean: Optional[float] = None
    min: Optional[float] = None
    max: Optional[float] = None
    std: Optional[float] = None


class Visit(BaseModel):
    """One train's stay in one component."""

    train_uid: str
    component_uid: str
    component_type: str
    # Position of this visit in the train's tour, starting at 0.
    index: int
    time_in: int
    # None if the train was still in the component when the run ended.
    time_out: Optional[int] = None
    occupancy: Optional[int] = None
    scheduled_arrival: Optional[int] = None
    scheduled_departure: Optional[int] = None
    arrival_delay: Optional[int] = None
    departure_delay: Optional[int] = None


class ComponentStats(BaseModel):
    component_uid: str
    component_type: str
    visits: int
    incomplete_visits: int
    occupancy: Stats
    headway: Stats
    arrival_delay: Stats
    departure_delay: Stats
    # Percentage (0-100); None if no visit to this component was scheduled.
    on_time_pct: Optional[float] = None


class TrainStats(BaseModel):
    train_uid: str
    tour: Optional[str] = None
    visits: int
    incomplete_visits: int
    first_time_in: Optional[int] = None
    last_time_out: Optional[int] = None
    arrival_delay: Stats
    departure_delay: Stats
    on_time_pct: Optional[float] = None


class RunStats(BaseModel):
    events: int
    trains: int
    components: int
    visits: int
    incomplete_visits: int
    first_event_time: Optional[int] = None
    last_event_time: Optional[int] = None
    on_time_threshold: int
    arrival_delay: Stats
    departure_delay: Stats
    on_time_pct: Optional[float] = None


class RunAnalysis(BaseModel):
    run: RunStats
    components: List[ComponentStats]
    trains: List[TrainStats]
    visits: List[Visit]


def _stats(values: Sequence[float]) -> Stats:
    n = len(values)
    if n == 0:
        return Stats(n=0)
    return Stats(
        n=n,
        mean=mean(values),
        min=min(values),
        max=max(values),
        std=stdev(values) if n > 1 else None,
    )


def _on_time_pct(visits: Sequence[Visit], threshold: int) -> Optional[float]:
    eligible = 0
    on_time = 0
    for v in visits:
        delays = [d for d in (v.arrival_delay, v.departure_delay) if d is not None]
        if not delays:
            continue
        eligible += 1
        if all(d <= threshold for d in delays):
            on_time += 1
    return None if eligible == 0 else 100.0 * on_time / eligible


def _scheduled_segments(project: dict) -> Dict[str, List[_Segment]]:
    """Each train's tour flattened into the sequence of components it visits.

    This mirrors `spur.core.tour.Tour.traverse`: a component shared by the end
    of one route and the start of the next is visited once, and takes its
    departure time from the next route's first entry (even if that is None).
    """
    routes = {r["name"]: r for r in project.get("routes", [])}
    tours = {t["name"]: t for t in project.get("tours", [])}

    schedule: Dict[str, List[_Segment]] = {}
    for train in project.get("trains", []):
        try:
            tour = tours[train["tour"]]
        except KeyError:
            raise InputMismatchError(
                f"Train {train['name']!r} refers to unknown tour {train['tour']!r}"
            ) from None

        segments: List[_Segment] = []
        for i, tour_route in enumerate(tour["routes"]):
            try:
                components = routes[tour_route["name"]]["components"]
            except KeyError:
                raise InputMismatchError(
                    f"Tour {tour['name']!r} refers to unknown route {tour_route['name']!r}"
                ) from None
            args = tour_route["args"]
            if len(components) != len(args):
                raise InputMismatchError(
                    f"{len(args)} args object(s) are supplied for route "
                    f"{tour_route['name']!r} in tour {tour['name']!r} but the route "
                    f"has {len(components)} components"
                )
            entries: List[_Segment] = [
                (
                    f"{c['u']}-{c['v']}-{c['key']}",
                    (a or {}).get("arrival"),
                    (a or {}).get("departure"),
                )
                for c, a in zip(components, args)
            ]
            if i == 0:
                segments.extend(entries)
            elif entries:
                uid, arrival, _ = segments[-1]
                segments[-1] = (uid, arrival, entries[0][2])
                segments.extend(entries[1:])
        schedule[train["name"]] = segments
    return schedule


def analyze(
    events: Sequence[SimEvent],
    project: dict,
    on_time_threshold: int = DEFAULT_ON_TIME_THRESHOLD,
) -> RunAnalysis:
    """Compute dwell, headway and delay metrics for a run.

    Parameters
    ----------
    events : sequence of `SimEvent`
        The run's events **in the order they were emitted** (`Model.events`, or
        stored events ordered by their sequence number). Order matters: a
        train's k-th `IN` is matched with its k-th `OUT`.
    project : dict
        The project the events came from, with "components", "routes",
        "tours" and "trains" keys - the shape `Model.to_project_dictionary()`
        returns. It supplies the schedule that delays are measured against.
    on_time_threshold : int, optional
        A visit counts as on time if none of its delays exceeds this, in
        simulation time units. Default 120.

    Raises
    ------
    InputMismatchError
        If the events don't match the project (a train that isn't in it, a
        train visiting more components than its tour has, or a visited
        component that differs from the tour's). Delays measured against the
        wrong schedule would be silently wrong, so this is an error.
    """
    schedule = _scheduled_segments(project)
    tour_of = {t["name"]: t["tour"] for t in project.get("trains", [])}

    ins: Dict[str, List[SimEvent]] = defaultdict(list)
    outs: Dict[str, List[SimEvent]] = defaultdict(list)
    for e in events:
        if e.event == SimEventType.IN:
            ins[e.train_uid].append(e)
        elif e.event == SimEventType.OUT:
            outs[e.train_uid].append(e)

    for train_uid in outs.keys() - ins.keys():
        raise InputMismatchError(f"Train {train_uid!r} has OUT events but no IN events")

    visits: List[Visit] = []
    for train_uid, in_events in ins.items():
        if train_uid not in schedule:
            raise InputMismatchError(
                f"Events refer to train {train_uid!r}, which is not in the project"
            )
        segments = schedule[train_uid]
        out_events = outs.get(train_uid, [])
        if len(in_events) > len(segments):
            raise InputMismatchError(
                f"Train {train_uid!r} entered {len(in_events)} components but its "
                f"tour only has {len(segments)}"
            )
        if len(out_events) > len(in_events):
            raise InputMismatchError(
                f"Train {train_uid!r} has more OUT events than IN events"
            )

        for k, ev in enumerate(in_events):
            uid, sched_arrival, sched_departure = segments[k]
            if ev.component_uid != uid:
                raise InputMismatchError(
                    f"Train {train_uid!r} visit {k} was to {ev.component_uid!r} but "
                    f"its tour has {uid!r} there"
                )
            out = out_events[k] if k < len(out_events) else None
            if out is not None and (
                out.component_uid != ev.component_uid or out.time < ev.time
            ):
                raise InputMismatchError(
                    f"Train {train_uid!r} visit {k}: OUT does not follow its IN"
                )
            visits.append(
                Visit(
                    train_uid=train_uid,
                    component_uid=ev.component_uid,
                    component_type=ev.component_type,
                    index=k,
                    time_in=ev.time,
                    time_out=None if out is None else out.time,
                    occupancy=None if out is None else out.time - ev.time,
                    scheduled_arrival=sched_arrival,
                    scheduled_departure=sched_departure,
                    arrival_delay=(
                        None if sched_arrival is None else ev.time - sched_arrival
                    ),
                    departure_delay=(
                        None
                        if out is None or sched_departure is None
                        else out.time - sched_departure
                    ),
                )
            )

    visits.sort(key=lambda v: (v.time_in, v.train_uid, v.index))

    by_component: Dict[str, List[Visit]] = defaultdict(list)
    by_train: Dict[str, List[Visit]] = defaultdict(list)
    for v in visits:
        by_component[v.component_uid].append(v)
        by_train[v.train_uid].append(v)

    components = []
    for uid in sorted(by_component):
        vs = by_component[uid]
        times_in = [v.time_in for v in vs]
        components.append(
            ComponentStats(
                component_uid=uid,
                component_type=vs[0].component_type,
                visits=len(vs),
                incomplete_visits=sum(v.time_out is None for v in vs),
                occupancy=_stats([v.occupancy for v in vs if v.occupancy is not None]),
                headway=_stats([b - a for a, b in zip(times_in, times_in[1:])]),
                arrival_delay=_stats(
                    [v.arrival_delay for v in vs if v.arrival_delay is not None]
                ),
                departure_delay=_stats(
                    [v.departure_delay for v in vs if v.departure_delay is not None]
                ),
                on_time_pct=_on_time_pct(vs, on_time_threshold),
            )
        )

    trains = []
    for train_uid in sorted(set(schedule) | set(by_train)):
        vs = by_train.get(train_uid, [])
        completed = [v.time_out for v in vs if v.time_out is not None]
        trains.append(
            TrainStats(
                train_uid=train_uid,
                tour=tour_of.get(train_uid),
                visits=len(vs),
                incomplete_visits=sum(v.time_out is None for v in vs),
                first_time_in=min((v.time_in for v in vs), default=None),
                last_time_out=max(completed, default=None),
                arrival_delay=_stats(
                    [v.arrival_delay for v in vs if v.arrival_delay is not None]
                ),
                departure_delay=_stats(
                    [v.departure_delay for v in vs if v.departure_delay is not None]
                ),
                on_time_pct=_on_time_pct(vs, on_time_threshold),
            )
        )

    times = [e.time for e in events]
    run = RunStats(
        events=len(events),
        trains=len(by_train),
        components=len(by_component),
        visits=len(visits),
        incomplete_visits=sum(v.time_out is None for v in visits),
        first_event_time=min(times, default=None),
        last_event_time=max(times, default=None),
        on_time_threshold=on_time_threshold,
        arrival_delay=_stats([v.arrival_delay for v in visits if v.arrival_delay is not None]),
        departure_delay=_stats(
            [v.departure_delay for v in visits if v.departure_delay is not None]
        ),
        on_time_pct=_on_time_pct(visits, on_time_threshold),
    )
    return RunAnalysis(run=run, components=components, trains=trains, visits=visits)
