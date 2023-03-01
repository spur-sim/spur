Installation
============

Spur is currently under active initial development, it is not available
for installation on PyPi or other platforms. If you are interested in installing a developer version in order to contribute
to the project, please see our `contribution guide<Contribution Guide>` for instructions.

If you would like to build the project to test or interact with what is developed
so far, you will need to install the following modules:


* `NetworkX <https://networkx.org/>`_
* `PyQt6 <https://pypi.org/project/PyQt6/>`_
* `SciPy <https://scipy.org/>`_
* `Simpy <https://simpy.readthedocs.io/en/latest/>`_

All of these modules are available on PyPi and can be installed using ``pip``, however we recommend you install the
codebase using Conda.

.. note::
    At the time of writing, PyQt6 is only available on ``pip`` and not on ``conda-forge``. If you use ``conda`` or ``mamba``
    to set up your environment you will need to install ``pip`` and then PyQt6 with::

        pip install PyQt6

    If you use the ``.yml`` file provided in the ``ci`` folder, this will be done for you.

You can install ``spur`` directly into your environment using::

    pip install .

from the main Spur directory.