.. _contributing:

Contributing to Spur
====================

**Note**: This contribution guideline is based on the `contribution guidelines for r5py <https://r5py.readthedocs.io/en/stable/CONTRIBUTING.html>`_ written by the r5py contributors, which are in turn laregly based on `pyrosm <https://pyrosm.readthedocs.io/en/latest/>`_ and `momepy <http://docs.momepy.org/en/stable/>`_ libraries.

Contributions to Spur of any kind are welcome. This doesn't just mean writing
new code, but also improving documentation, guides, or creating additional tests
and finding bugs in the software. In addition, we welcome ideas of new features
that could be added or how to improve the existing codebase.

All contributions must be done through the GitHub repository. Bug reports, ideas,
or questions should be raised by opening an issue on the `GitHub issue tracker <https://github.com/transit-analytics-lab/spur/issues>`_.
Suggestions for changes in the code or documentation should be submitted via a pull
request, however if you are not sure what to do, feel free to open an issue.
Importantly, all documentation and discussion will take place on GitHub to keep
Spur's development transparent.

Steps to Contribute
###################

1. Fork the Spur git repository
2. Create a development environment and build.
3. Make changes to code and tests
4. Update the documentation if needed according to the changes made
5. Format the code and update any documentation strings
6. Submit a pull request

1. Fork the Spur Repository
#############################

There are lots of tools out there for working with Git, including tools baked
into GitHub(.com or desktop) and into development environments like VSCode or
PyCharm.

You can also fork the repository old-school::

    git clone git@github.com:your-user-name/spur.git spur-yourname
    cd spur-yourname
    git remote add upstream git://github.com/transit-analytics-lab/spur.git

This creates a directory named ``spur-yourname`` and connects your new repository
to the upstream main project hosted by the Transit Analytics Lab.

2. Create a Development Environment and Build
#############################################

The easiest way to create a development environment is by using `Mamba Forge <https://github.com/conda-forge/miniforge#mambaforge>`_ or some version of Conda. Make sure that you have cloned the Spur repository. Once you have done this you can create a new environment from the YAML file inside the ``ci`` directory::
    
    mamba env create -f ci/python_310_dev.YAML

This will create an environment called ``spur-dev`` and won't mess with any of your existing Python installations or environments. It includes all the necessary dependencies for Spur as well as some additional packages for building docs, running tests, and formatting code. You can start working on (and with) Spur with this environment after you activate it::

    conda activate spur-dev

Remember that you can view your conda environments with ``conda info -e`` and return to your home environment ``(base)`` with ``deactivate``.

Now that you have your dependencies you can install the development version of Spur on your computer by navigating to the top project folder and running::

    pip install .

3. Making Changes
#################

Contributions and changes should embrace the principles of `test-driven development <http://en.wikipedia.org/wiki/Test-driven_development>`_. This relies on the repetition of a very short development cycle where you write a
test (that fails) that defines a desired function and then write the minimum amount of code that passes that test.

Spur uses the pytest testing system. All tests should go in the ``tests`` directory, which contains examples of tests. You can look to these for inspiration.

You can run the test suite from the main project directory using::

    pytest -v

4. Updating the Documentation
#############################

Spur documentation resides in the ``docs`` folder. Changes to the documentation can be made by finding the appropriate file within this documentation folder. Spur uses reStructureText syntax (`explained here <http://www.sphinx-doc.org/en/stable/rest.html#rst-primer>`_) as well as documentation strings for code formatted using the (`example here <https://sphinxcontrib-napoleon.readthedocs.io/en/latest/example_numpy.html>`_).

Once you have updated the documents, make sure they render correctly by building the documentation using Sphinx (installed with the development environment) using::

    make html

The resulting pages can be found in ``docs/build/html``. Note that these files should **not** be committed as part of the project (and are by default ignored in the ``.gitignore`` file.)

5. Formatting the Code
######################

Python (PEP8 and Black)
-----------------------

Spur follows the [PEP8](http://www.python.org/dev/peps/pep-0008) standard
and uses [Black](https://black.readthedocs.io/en/stable/) to ensure a consistent code format throughout the project.

It is helpful before submitting code to
auto-format your code::

    black src

But many editors have plugins that will apply `black` as you edit files.
If you don't have black, you can install it using ``pip``, though it is included in the development installation ``.yml`` file::

    pip install black

Import Order
------------

To keep things organized by convention, please organize your import statements in the following order:

1. Import of modules that are part of the Python Standard Library (e.g. ``dateteime`` or ``json``)
2. Imports of third-party Python modules (e.g. ``simpy``)
3. Relative imports of other Spur modules (e.g. ``spur.core.exception``)


6. Submit a Pull Request
########################

Once you've made changes and pushed them back to your forked repository, you can
submit a pull request to have them integrated into the ``transit-analytics-lab/spur`` code base.

You can read about pull reqests using the `GitHub Help Docs <https://help.github.com/articles/using-pull-requests>`_.


