Getting Started 
===============

Creating a simulation requires a few key sources of data:

* A list of :ref:`components<Component>` that form the simulated network,
* A train or set of trains which traverses the network (see :ref:`Train` documentation for details), and
* A set of :ref:`tours<Tour>` and :ref:`routes<Route>` defined.

These data can be manually added in code, or defined in a JSON format.

As an example, we have provided a simple simulation that recreates the movement of trains on the Line 4 Subway in Toronto, Canada. This subway consists of a simple sequence of stations traversed eastward on southern tracks, and westward on northern tracks.

You can run the simulation by following the `line4.py` file in the GitHub.