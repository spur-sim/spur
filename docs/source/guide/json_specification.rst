.. _json_specification:

JSON File Specifications
=========================

A Spur model can be built entirely in code, but the more common way is to describe
it as JSON and load it with the helpers in :mod:`spur.io.formats`. There are four
input files - **components**, **routes**, **tours**, and **trains** - plus a
combined **project file** (the ``.spur`` format) that bundles all four together.

Every one of these shapes is validated on load against a `Pydantic
<https://docs.pydantic.dev/>`_ schema defined in ``spur/io/schema.py``. If a file
doesn't match, you'll get a clear :class:`~spur.core.exception.InvalidProjectDataError`
naming the exact field that's wrong, rather than a confusing error later on while
the model is being built.

``components.json``
--------------------

A JSON array of component definitions. Each object describes one edge in the
network graph:

.. code-block:: javascript

    {
        "type": "TimedTrack",
        "u": "yonge-east",
        "v": "bayview-west",
        "key": "N",
        "name": "Optional human-readable name",
        "args": {
            "traversal_time": 161,
            "capacity": 10
        },
        "jitter": {
            "type": "LognormalJitter",
            "args": {"mean": 2, "std": 10}
        },
        "collection": {
            "type": "BlockExclusiveZone",
            "key": "some-zone-id"
        }
    }

``type``
    The component class name, e.g. ``TimedTrack`` or ``SimpleStation`` - see the
    table below for the full list and their ``args``.
``u``, ``v``, ``key``
    Together these identify the component as an edge of the network graph. ``u``
    and ``v`` are the node names the component connects; ``key`` distinguishes
    multiple components between the same two nodes (e.g. separate tracks in each
    direction).
``name``
    *Optional.* A human-readable label - purely descriptive, not used to identify
    the component anywhere else.
``args``
    The keyword arguments passed to the component's constructor. See the table
    below for what each component type expects.
``jitter``
    *Optional.* Perturbs the component's timing - see :ref:`Jitter types
    <json_spec_jitter>` below. Defaults to no perturbation if omitted.
``collection``
    *Optional.* Groups this component with others into a shared occupancy rule
    (currently only :class:`~spur.core.collection.BlockExclusiveZone`, which
    allows only one train across the whole group at a time). Components that
    share the same ``type`` and ``key`` here belong to the same collection
    instance.

Component types and their ``args``
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

======================= ================================================================================================================================================================================================
Type                    ``args``
======================= ================================================================================================================================================================================================
``TimedTrack``          ``traversal_time`` (int), ``capacity`` (int, default 1)
``MultiBlockTrack``     ``num_tracks`` (int), ``num_blocks`` (int), ``traversal_time`` (int)
``SimpleYard``          ``capacity`` (int)
``SimpleStation``       ``mean_boarding`` (int), ``mean_alighting`` (int) - dwell time from the San2016 boarding/alighting formula
``MultiTrackStation``   ``num_stopping_tracks`` (int), ``num_bypass_tracks`` (int), ``bypass_time`` (int), ``dwell_c``, ``dwell_d``, ``dwell_loc``, ``dwell_scale`` (floats - Burr-distributed dwell time parameters)
``TimedStation``        ``traversal_time`` (int) - a fixed-time dwell, no boarding/alighting model
``SimpleCrossover``     ``traversal_time`` (int)
======================= ================================================================================================================================================================================================

See the :ref:`Component reference <ref_component>` for full details on each
class, including validation rules (most numeric parameters must be positive).

.. _json_spec_jitter:

Jitter types and their ``args``
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

===================== =========================================
Type                  ``args``
===================== =========================================
``NoJitter``           *(none)*
``UniformJitter``      ``minimum`` (int), ``maximum`` (int)
``GaussianJitter``     ``mean`` (float, default 0.0), ``std`` (float, default 1.0)
``LognormalJitter``    ``mean`` (float, default 10.0), ``std`` (float, default 1.0)
``DisruptionJitter``   ``p`` (float, 0-1), ``delay`` (int)
===================== =========================================

See the :ref:`Jitter reference <ref_jitter>` for the perturbation each type
applies.

``routes.json``
----------------

A JSON array of named, reusable sequences of components:

.. code-block:: javascript

    [
        {
            "name": "R-Eastbound",
            "components": [
                {"u": "yonge-west", "v": "yonge-east", "key": "Y"},
                {"u": "yonge-east", "v": "bayview-west", "key": "S"}
            ]
        }
    ]

Each entry under ``components`` identifies a component already defined in
``components.json`` by its ``u``/``v``/``key``. A route only describes *which*
components are traversed and in what order - per-traversal timing (arrival and
departure constraints) is supplied separately by whichever tour uses the route,
so the same route can be reused by many tours with different schedules.

``tours.json``
---------------

A JSON array describing a train's full itinerary - one or more routes traversed
in sequence, each with optional per-component timing:

.. code-block:: javascript

    [
        {
            "name": "Tour-1",
            "creation_time": 0,
            "deletion_time": 86400,
            "routes": [
                {
                    "name": "R-Eastbound",
                    "args": [
                        {"departure": 20850},
                        null
                    ]
                }
            ]
        }
    ]

``name``
    Identifies the tour, referenced by ``trains.json``.
``creation_time``, ``deletion_time``
    The simulation-time window during which this tour is valid.
``routes``
    A list of routes traversed in order. The last component of one route must be
    the same as the first component of the next (tours stitch routes together at
    a shared boundary component).
``routes[].args``
    A list with exactly one entry per component in the referenced route, in the
    same order. Each entry is either ``null`` (no timing constraint at that
    component) or an object with ``arrival`` and/or ``departure`` (both
    optional) - simulation-time values the train will wait for before
    proceeding.

``trains.json``
-----------------

A JSON array assigning a tour to each train:

.. code-block:: javascript

    [
        {"name": "T-0", "max_speed": 50, "tour": "Tour-1"}
    ]

``name``
    The train's unique ID.
``max_speed``
    A positive number. Not currently enforced by any component's traversal-time
    calculation - see the :ref:`Component reference <ref_component>` for which
    parameters actually drive timing.
``tour``
    The ``name`` of a tour defined in ``tours.json``.

The combined project file (``.spur``)
---------------------------------------

A single JSON file bundling all four sections together, for saving, sharing, or
re-running a whole scenario in one file:

.. code-block:: javascript

    {
        "type": "SpurProject",
        "name": "Optional project name",
        "spur_version": "v1.0.0",
        "components": [ ... ],
        "routes": [ ... ],
        "tours": [ ... ],
        "trains": [ ... ]
    }

Loading and saving
--------------------

The four section files are read individually with the functions in
:mod:`spur.io.formats`:

.. code-block:: python

    from spur.io.formats import (
        read_components_json, read_routes_json,
        read_tours_json, read_trains_json,
    )

    components = read_components_json("components.json")
    routes = read_routes_json("routes.json")
    tours = read_tours_json("tours.json")
    trains = read_trains_json("trains.json")

or a whole project can be built directly from a dictionary shaped like the four
sections above:

.. code-block:: python

    from spur.core import Model

    model = Model.from_project_dictionary({
        "components": components,
        "routes": routes,
        "tours": tours,
        "trains": trains,
    })

A model built this way remembers exactly what it was given, so it can be
exported back out again with ``model.to_project_dictionary()`` - useful for
saving a scenario you built or modified in code. The combined ``.spur`` file
format is read and written with :func:`~spur.io.formats.read_project_json` and
:func:`~spur.io.formats.write_project_json`.
