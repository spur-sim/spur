.. Spur documentation master file, created by
   sphinx-quickstart on Wed Aug  4 10:02:03 2021.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

Spur: Simulation for Planning and Understanding Railways
========================================================

**Spur** is an event-based mesoscopic railway network simulation platform designed
to support real-time operations and medium-to-long-term planning by capturing the 
stochastic movement of individual trains and the interactions between trains on 
the network while maintaining a paramatertized view of rail movements and dynamics. 
The model balances simplification with flexibility, and requires substantially 
less data and expertise than traditional microscopic simulation models.

Spur is currently **under initial development**. This means that while features
are available and can in principle be used for simulation purposes, the design of the
simulation and codebase are likely to change rapidly without much thought for backwards
compatability or overall impacts. 

This documentation serves as a development reference, technical documentation source, and
eventual user guide for the software platform.

The documentation here is designed both as a user manual and as a technical
documentation source for developers wishing to adapt or extend the software or
build their own plugins.

If you are interested in contributing to the project, please consult our :ref:`contribution guide<Contributing to Spur>`.



.. toctree::
   :glob:
   :caption: Contents
   
   quickstart
   guide/index
   contributing
   reference/index
