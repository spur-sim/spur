.. _analysis_guide:

Analysing a run
===============

A finished run leaves behind a list of structured events (see :ref:`logging_guide`): every time a train enters or leaves a component. :func:`spur.analysis.analyze` turns those events into the numbers most people actually want - how long trains dwell at stations, how far apart they run, and how late they are.

.. code-block:: python

    from spur.core import Model
    from spur.analysis import analyze

    model = Model.from_project_dictionary(project, seed=42)
    model.start()
    model.run(until=36900)

    analysis = analyze(model.events, model.to_project_dictionary())

    for c in analysis.components:
        print(c.component_uid, c.occupancy.mean, c.headway.mean)

``analyze`` is a plain function of the events and the project, so it works just as well on events you saved earlier and read back, as long as they are in the order they were emitted. It needs the project because delays are measured against the schedule in the tours. If the events don't match the project (a train that isn't in it, or a component the tour doesn't visit at that point), it raises :class:`~spur.core.exception.InputMismatchError` rather than quietly reporting delays against the wrong schedule.

What you get back
-----------------

A :class:`~spur.analysis.RunAnalysis` with four parts:

``visits``
    One row per train per component it stayed in, with the times in and out, the scheduled times, and the delays.
``components``
    Statistics for each component: how long trains occupied it, the headway between trains, and delays.
``trains``
    The same kind of statistics for each train.
``run``
    Totals for the whole run, and overall delay statistics.

Each statistic is a :class:`~spur.analysis.Stats` with the count, mean, minimum, maximum and sample standard deviation. Values that can't be computed are ``None``: everything but the count when there is no data, and the standard deviation when there is only one value.

Definitions
-----------

Visit
    One train's stay in one component, from the moment it is admitted (``time_in``) to the moment it is admitted to the next component (``time_out``). A visit that is still open when the run ends has no ``time_out``; it is counted as incomplete and left out of the occupancy and delay statistics.

Occupancy
    ``time_out - time_in``. At a station this is the **dwell time**; at a yard it is the time the train spends waiting there. It includes any time the train is held for its scheduled departure.

Arrival delay
    ``time_in - scheduled arrival``, for visits that have a scheduled arrival.

Departure delay
    ``time_out - scheduled departure``, for complete visits that have a scheduled departure. ``time_out`` is when the train actually leaves, so this is how late it left.

Headway
    The gap between consecutive trains entering the same component. Trains that enter together have a headway of zero.

On-time percentage
    The share of scheduled visits whose delays are all within ``on_time_threshold`` (120 time units unless you pass another). Visits with no scheduled time, and open visits with no delay to measure, are not counted.

.. note::
    Trains in Spur are held to their schedule: a train that arrives early waits until its scheduled arrival, and never leaves before its scheduled departure. So delays are never negative, and an early arrival can't be seen in the events at all - only lateness can.
