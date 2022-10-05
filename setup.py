import setuptools

from spur import __version__

with open("README.md", "r") as fh:
    long_description = fh.read()

setuptools.setup(
    name="spur",  # Replace with your own username
    version=__version__,
    author="Willem Klumpenhouwer",
    author_email="willem.klumpenhouwer@utoronto.ca",
    description="Spur: Simulate Preliminary and Unfussy Railways",
    long_description=long_description,
    long_description_content_type="text/markdown",
    packages=setuptools.find_packages(),
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Development Status :: 1 - Planning",
        "Intended Audience :: Science/Research",
        "Natural Language :: English",
    ],
    python_requires=">=3.6",
    install_requires=[
        "simpy",
        "pyqt6"
    ],
)
