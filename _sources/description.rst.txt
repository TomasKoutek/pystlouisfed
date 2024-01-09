Description
===========

.. note::
    This is a third-party client that is developed and maintained independently of the Federal Reserve Bank. As such, it is not affiliated with or supported by the institution.

| The Federal Reserve Bank of St. Louis is one of 12 regional Reserve Banks that, along with the Board of Governors in Washington, D.C., make up the United States' central bank.
| The https://stlouisfed.org site currently provides more than 816,000 time series from 107 sources using the FRED (Federal Reserve Economic Data) and ALFRED (Archival FRED) interfaces. It is also possible to obtain detailed geographical data from FRED Maps or more than 500,000 publications from the digital library FRASER.

| The pystlouisfed package covers the entire FRED / ALFRED / FRED Maps / FRASER API and returns most of the results as pandas.DataFrame, which is cast to the correct data types with a specific index. So "date", "realtime_start", "observation_start" etc are datetime64 type, "value" is float and not str, missing values are np.NaN and not "." etc ...
| The naming convention of methods and parameters is the same as in the target API and everything is detailed documented. There is also a default rate-limiter, which ensures that the API call limit is not exceeded.
