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


Randomness
##########