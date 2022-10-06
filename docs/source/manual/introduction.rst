Design Philosophy
=================

    "There is no point in using mathematical methods that are any more accurate than the practical conclusions to which they will lead." 
    - *G.F. Newell*

Before we dive into the details of getting your first model up and running, it's worth talking a little bit about how we thought about the model as it was being built. Spur is a *mesoscopic* simluation model, which means it has the tricky task of avoiding asking you for too much detail and input about the situation you are modelling while still providing usefully realistic results. Where possible, the software is designed to abstract away as much of the individual detail of train movement and dynamics while still providing the flexibility to add detail if so desired by creating your own plugins.

Railway modelling (at least the kind that Spur does) requires breaking down a scenario or network that you would like to model into smaller parts, modelling those parts individually, and then stitching them back together to get a larger picture of what is happening. Part of the design flexibility is that the choice of *how* you would like to break a scenario down is left up to you.

.. note::
    For example, you could model a station as individual platforms and tracks, or you could treat it as a larger black box which accepts a certain number of trains, processes, them, and releases them again. The former approach might be useful if you were interested in modelling how different platforms and passenger volumes affect a larger station, while the latter is useful if you are looking at a much larger network.

Agents and Components
#####################

The two families of objects you will interact with the most while using Spur are `agents` and `components`. Agents traverse the model network following a set of instructions given to them by the model, while components respond to requests by the agents to use them. 

.. note::
    Here's a concrete example: A passenger train is an agent which follows a set route. One of the components on its route is a station platform. The train requests use of the station component, and the station component responds by accepting the train when the station is empty, and holding the train for a set period of time.

The basic simulation process goes as follows: An agent *requests* to use a component, and that component responds to the request by queuing the agent, processing it according to the design of the component, and releasing it. Then the agent moves to the next part of the route and repeats the process with the next component. This simple iteration of request, process, release is the core design principle of the model, and is what makes Spur primarily a *queuing* model.

Event-Based Modelling
#####################

Spur is built on the simulation framework of event-based modelling. This means that the simulation keeps a running schedule of discrete events that need to happen and executes on them at the appropriate simulation time. One analogy for this is a turn-based video or board game - things happen in a set sequence, though that sequence can change or adapt based on the situation.

The main advantage of event-based modelling is that it is more scalable and faster to run than models that require keeping track of a larger set of complex physics or environment effects. Of course, the more detail or process-intensive tasks that are included in determining the next action, the more effort it will take to simulate a situation.

Randomness
##########

While Spur is designed to support a wide variety of potential applications, one of the key focuses of the design is the incorporation and understanding of how randomness affects a given situation. To model this randomness, Spur draws on an idea commonly used in physics of "perturbations", which involves setting up a model in an ideal and non-random state, and then applying specific perturbations or "bumps" to the system to simulate randomness. In the design and documentation of Spur, we refer to this as "jitter".

.. note::
    Here's an example: You may have a station component which represents a train station and its interaction with the train as it stops. Typically, the station is designed to hold the train for a certain period of time (say 30 seconds) while the train handles passengers. Passenger loading is notoriously random; the number of passengers and the time they need to board can vary a fair bit. To model this, we apply a "jitter" which adjusts the 30-second baseline by some amount in a random fashion. How that random fashion is chosen is up to you, and can be based on probability distributions or data inputs.

Plug-In Modularity
##################

Given the design philosophy of flexibility described above, the eventual goal of Spur is to allow for users to create and add their own specific behaviours into the model in the form of plugins. In this way, Spur can be adapted to suit individual research or planning needs.