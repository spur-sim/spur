.. _logging_guide:

Logging and Output Files
==========================

Spur uses Python's standard :mod:`logging` module for all of its output, but as
a library it never writes files on its own initiative. Every file output is
**opt-in**, requested explicitly when you create a :class:`~spur.core.model.Model`:

.. code-block:: python

    from spur.core import Model

    model = Model(
        sim_log_file="sim.log",
        debug_log_file="debug.log",
        agent_log_file="agent.log",
    )

Pass only the ones you want - none are required, and each is written to
whatever path you give it. If you don't need file output at all, you can leave
all three out; a summary of ``sim.log``-level messages is always printed to the
console for you, since it's cheap and scoped to this model instance alone (see
:ref:`Multiple simulations in one process <logging_multiple_models>` below).

There is no longer any *automatic* logging output (older versions of Spur wrote
``spur.log``/``debug.log``/``error.log`` the moment you imported the package -
this was removed because a library shouldn't have import-time side effects).
If you want to see log output without writing any files, configure Python's
own logging yourself, e.g. ``logging.basicConfig(level=logging.INFO)`` before
running your model.

``sim.log`` - general simulation log
--------------------------------------

Requested with the ``sim_log_file`` argument. Contains ``INFO``-level messages
about the model's own lifecycle - setup, start, resume, and stop - plus
whatever ``INFO``-level messages individual components and trains choose to
log. This is the log to read if you want a human-readable narrative of what
happened during a run, at a glance.

Each line in the file looks like:

.. code-block:: text

    0      INFO     sim.a1b2c3d4                    Model setup complete!
    0      INFO     sim.a1b2c3d4                    Model started
    36900  INFO     sim.a1b2c3d4                    Model stopped

The columns are: simulation time, the log level, the logger name (scoped to
this model instance - see below), and the message. The console output printed
by default (with no ``sim_log_file`` needed) uses the same information minus
the level column, since it's always ``INFO``-and-above there.

``debug.log`` - detailed debug log
--------------------------------------

Requested with the ``debug_log_file`` argument. Same format as ``sim.log``,
but includes ``DEBUG``-level messages too - much more verbose, showing
per-component and per-train internal chatter (resource requests, dwell time
calculations, and similar). Useful when tracking down unexpected behaviour;
not something you'd typically read line-by-line for a normal run.

``agent.log`` - structured train movement log
-------------------------------------------------

Requested with the ``agent_log_file`` argument. This is the one most useful
for analysis and visualization: a comma-separated line for every time a train
enters or leaves a component, plus (if you call
:meth:`~spur.core.model.Model.log_current_state`) a snapshot of every train's
current location at whatever moment you choose.

.. code-block:: text

    0,agent.a1b2c3d4.train.T-0,IN,0-1-Y,SimpleYard
    161,agent.a1b2c3d4.train.T-0,OUT,0-1-Y,SimpleYard
    161,agent.a1b2c3d4.train.T-0,IN,1-2-A,TimedTrack
    36900,agent.a1b2c3d4.train.T-0,LOC,1-2-A,TimedTrack

Each line has five comma-separated fields: simulation time, the logger name
(identifies which train - see below), the event type, the component's unique
ID, and the component's type name.

Event types
^^^^^^^^^^^^

``IN``
    The train has been granted access to the named component and has started
    traversing/dwelling at it.
``OUT``
    The train has finished with the named component and released it.
``LOC``
    A position snapshot, written only when :meth:`Model.log_current_state()
    <spur.core.model.Model.log_current_state>` is called - not part of the
    normal IN/OUT flow. Useful for recording where every train is at an
    arbitrary point in time, or for extending a train's last-known position
    through to the end of a run when it's still mid-traversal or waiting when
    the model stops.

Structured events - the in-memory alternative to ``agent.log``
-------------------------------------------------------------------

If you're embedding Spur as a library (for example, behind an API service)
rather than reading log files, :class:`~spur.core.model.Model` also emits
the same IN/OUT/LOC facts as typed :class:`~spur.core.event.SimEvent`
objects instead of text lines - no file, no parsing required.

Every model always populates :attr:`Model.events <spur.core.model.Model.events>`,
a plain list, so the simplest usage is to run a model to completion and read
it afterwards:

.. code-block:: python

    model = Model()
    ...
    model.run()
    for event in model.events:
        print(event.time, event.event, event.train_uid, event.component_uid)

For real-time consumption (e.g. streaming progress to a client while a run
is in progress), pass an ``event_sink`` callable to the constructor; it is
called once per event, in the same order events are appended to
``model.events``:

.. code-block:: python

    model = Model(event_sink=lambda event: print("got", event))

``event_sink`` is purely additive - it has no effect on ``agent.log`` or any
other logging output, and vice versa; use whichever (or both) suit your
consumer.

.. _logging_multiple_models:

Multiple simulations in one process
--------------------------------------

Every logger name is scoped to the owning :class:`~spur.core.model.Model`
instance's own ``uid`` (auto-generated if you don't supply one, e.g.
``a1b2c3d4`` in the examples above) - so running several ``Model`` instances
in the same process, sequentially or in separate threads, never mixes their
output together or overwrites each other's files. Each train's logger name is
further scoped under its own model and its own ``uid`` (e.g.
``agent.a1b2c3d4.train.T-0``), so you can tell trains from different models
and different trains within the same model apart just by reading the logger
name column.
