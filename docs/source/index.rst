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

The documentation here is designed both as a user manual and as a technical
documentation source for developers wishing to adapt or extend the software or
build their own plugins.

To get started with a simlulation, have a look at the :ref:`getting started<Getting Started>`
section which outlines the basic requirements needed to install 

**If you are getting started with Spur** and would just like to build a simulation
and try it out, check out the :ref:`getting started<Getting Started>` page.

**If you are a developer** are are looking for the application programming
interface documentation, please check the PI



.. toctree::
   :glob:
   :caption: Contents
   
   quickstart
   guide/index
   contributing
   reference/index
