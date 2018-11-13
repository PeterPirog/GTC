# GTC

[![rtd badge][]](https://gtc.readthedocs.io/en/latest/)
[![travis shield][]](https://travis-ci.org/MSLNZ/GTC)
[![appveyor shield][]](https://ci.appveyor.com/project/jborbely/gtc/branch/master)

The GUM Tree Calculator is a Python package for processing data with measurement uncertainty.

Python objects, called uncertain numbers, are used to encapsulate information about measured
quantities. Calculations of derived quantities that involve uncertain numbers will propagate this
information automatically. So, data processing results are always accompanied by uncertainties. 

GTC follows international guidelines on the evaluation of measurement data and measurement
uncertainty (the so-called [GUM]( https://www.bipm.org/utils/common/documents/jcgm/JCGM_100_2008_E.pdf`)). 
It has been developed for use in the context of metrology, test and calibration work.

Example: an electrical circuit
==============================

Suppose the DC electrical current flowing in a circuit and the voltage across a circuit
element have both been measured. 

The values obtained were 0.1 V, for the voltage, and 15 mA for the current. These values have
the associated standard uncertainties 0.001 V and 0.5 mA, respectively. 

Uncertain numbers for voltage and current can be defined using the function `ureal()` 

	>>> V = ureal(0.1,1E-3)
	>>> I = ureal(15E-3,0.5E-3)

The resistance of the circuit element can then be calculated directly using Ohm's law

    >>> R = V/I
    >>> print(R)
    6.67(23)
    
The uncertain number `R` represents the resistance of the circuit element. The value 6.67 ohm
is an estimate (or approximation) of the actual resistance. The standard uncertainty associated
with this value, is 0.23 ohm.

Installation
============

**GTC** is available as a [PyPI package](https://pypi.org/project/GTC/). It can be installed
using pip

```commandline
pip install gtc
```   

Dependencies
------------
* Python 2.7, 3.4+
* [scipy](https://www.scipy.org/)

Documentation
=============

The documentation for **GTC** can be found [here](https://gtc.readthedocs.io/en/latest/).

[rtd badge]: https://readthedocs.org/projects/gtc/badge/
[travis shield]: https://img.shields.io/travis/MSLNZ/GTC/master.svg?label=Travis-CI
[appveyor shield]: https://img.shields.io/appveyor/ci/jborbely/gtc/master.svg?label=AppVeyor
