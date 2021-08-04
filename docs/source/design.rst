Design Approach 
===============

The goal of Spur is to support real-time operations and medium-term planning by capturing the stochastic movement of individual trains and the interactions between trains on the network. The model aims to balance simplification with flexibility, and require substantially less data and expertise than traditional microscopic simulation models.

Spur aims to accomplish the following:

* **Open up the modelling process to new people.** Train-level railway modelling usually requires a lot of technical expertise and data about a specific systems and dynamics of railways. Taking inspiration from various video games such as OpenTTD, Sid Meier's Railroads, and NIMBY Rails, the resulting model and software allows for the intuitive and quick construction of basic models, where detail can be added later.
* **Support operational decision making.** The speed and adaptability that comes from the simplification of microscopic modelling, combined with the ability to make real-time adjustments and changes to the model enables operators to use the model to both predict larger network effects during incidents as well as test (and even optimize) various possible responses.
* **Support medium-term planning and scheduling innovations.** Often, outside-the-box ideas don't make it to the simulation phase simply because simulating it is too onerous and not worth an agency's time commitment. Spur is useful for prototyping and testing operational plans and schedules quickly.


The design philosophy of the system starts by considering individual features offered by microscopic simulation, and finding ways to appropriately abstract some of the detail while maintaining the flexibility and goals set out above. The core model follows the microscopic approach of simulating individual train movements at a time-step (typically per-second) level.

The main simplification comes from the modelling of train movements through various components of the railway system. In this model, only the basics of train dynamics are considered explicity (in part due to the large impact of stopping and starting). Larger sections of track which may contain multiple signal blocks can be modeled as a single component, and can also be parameterized or modelled as needed using sub-models. Here's an example of what typical microscopic and macroscopic models offer, and where Spur sits in between them.

+-----------------+-------------+-------------+----------------+
| Attribute       | Microscopic | Spur        | Macroscopic    |
+=================+=============+=============+================+
| Grades & Curves | Realistic   | Abstracted  | Not considered |
+-----------------+-------------+-------------+----------------+
| Signals         | Realsitic   | Abstracted  | Not considered |
+-----------------+-------------+-------------+----------------+
| Dynamics        | Realsitic   | Simplified  | Not considered |
+-----------------+-------------+-------------+----------------+
| Travel times    | Train-based | Train-based | Fixed          |
+-----------------+-------------+-------------+----------------+
| Stochasticity   | Possible    | Possible    | Not included   |
+-----------------+-------------+-------------+----------------+
| Control         | Realsitic   | Simplified  | Not considered |
+-----------------+-------------+-------------+----------------+

Time Scale
##########
The simulation time scale closely follows standard simulation time step scales in microsimulation models, namely at the per-second or near-per-second time scale. This enables sub-models of train movement and station interaction to advance at an appropriate speed and enable near-real-time intervention in the model to simulate various operational responses.

As the simulation steps forward, the status of each train will be updated based on their previous status and the various sub-models that govern the section of track or area that a train is occupying. For example, a dwell-time model at a station may simply count until a fixed number of steps (seconds) have elapsed before releasing the train into the next section of track. In a queuing-style approach, a train may enter a section of track and advance through it over time.

Track Configurations
####################
Spur uses a schematic representation of track connections, following a standard *node* and *edge* terminology and structure common in any graph-like transportation network. Individual sections of track will connect possible divergent points (such as switches) and other important simulation components such as stations or yards. By considering only points of possible route divergence or specific places where train behaviour is something other than movement, we are able to greatly simplify the level of track-based input that is required into a model.

Each edge will be associated with a specific sub-model, and these sub-models will be designed to incorporate some basic information about the link (length or mean traversal time) along with model-specific parameters (standard deviation of movement for stochasticity, number of signals on the track, passenger volumes at a station to infer dwell times). In this way we can provide flexibility as to the amount of detail that is needed for specific applications, while allowing for a more generalized model used for prototyping or in typical scenarios.


Train Movement
##############
Movement of trains can be handled in a number of simplified or abstracted ways. At the most detailed level, the option exists to model train movements using basic kinematic equations calculating acceleration, deceleration, and cruising time on a section of trackway. Train movement does not have to be explicity considered however - traversal times can be set by the track component based on various parameters, including simply a fixed or mean travel time.

For example, trains moving through a section of track with multiple blocks might use cell transmission logic to manage the timing of movement through the section of track, while a single track block or station platform might use a fundamental-diagram approach or dwell time model. Each portion (edge) of the network will have a model that governs how trains move through the model and act in a way as individual agents or queues that serve trains as they enter the model.


Signalling and Control
######################
Signalling and control is not explcitiy handled in the model. For example, a section of track that has no diverging track or decision points such as stations may be treated as a single edge. This edge may contain multiple signals, or may be governed by moving block control. This allows for flexibility in the signalling system or the movement of trains through specification of how trains move across a given edge. Ultimately, the logic of how a train moves through a particular component is up to that component's design.