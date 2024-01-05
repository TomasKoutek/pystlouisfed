Installation
==============================

.. _pypi:

PyPI (recommended)
------------------

Package is on PyPI at https://pypi.org/project/pystlouisfed/

It can be installed in the same way as other packages:

.. code-block:: console

   python3 -m pip install pystlouisfed

Dependencies
------------
* `pandas <https://pandas.pydata.org/>`_ for time series data and lists
* `geopandas <https://geopandas.org/en/stable/>`_ for geometric data from FRED Maps
* `requests <https://docs.python-requests.org/en/latest/>`_ for API calls
* `sickle <https://sickle.readthedocs.io/>`_ for FRASER oai-pmh API
* `rush <https://github.com/sigmavirus24/rush>`_ for limiting API calls

GIT
------------------

Or alternatively you can clone from github:

.. code-block:: console

   git clone https://github.com/TomasKoutek/pystlouisfed
