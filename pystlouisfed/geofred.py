import logging
from collections.abc import Generator
from datetime import date as dt_date
from datetime import timedelta
from typing import NoReturn
from typing import Optional

import numpy as np
import pandas as pd

from pystlouisfed import enums
from pystlouisfed import models
from .client import Client

logger = logging.getLogger(__name__)


class GeoFRED:
    """
    The GeoFRED API is a web service that allows developers to write programs and build applications to harvest data and shape files found in GeoFRED website hosted by the Economic Research Division of the Federal Reserve Bank of St. Louis.

    https://geofred.stlouisfed.org/

    https://geofred.stlouisfed.org/docs/api/geofred/
    """
    EMPTY_VALUE = "."

    """
    https://geofred.stlouisfed.org/
    https://geofred.stlouisfed.org/docs/api/geofred/
    """

    def __init__(
            self,
            api_key: str,
            ratelimiter_enabled: bool = False,
            ratelimiter_max_calls: int = 120,
            ratelimiter_period: timedelta = timedelta(seconds=60),
            request_params: Optional[dict] = None
    ) -> NoReturn:
        """
        Parameters
        ----------
        api_key: str
                32 character alpha-numeric lowercase string
        ratelimiter_enabled: bool
        ratelimiter_max_calls: int
        ratelimiter_period: int
        request_params: dict
                HTTP GET method parameters, see https://docs.python-requests.org/en/latest/api/#requests.request
        """  # noinspection

        if api_key is None or len(api_key) != 32:
            raise ValueError("Variable api_key must be 32 character length alphanumeric string.")

        self._client = Client(
            key=api_key.lower(),
            ratelimiter_enabled=ratelimiter_enabled,
            ratelimiter_max_calls=ratelimiter_max_calls,
            ratelimiter_period=ratelimiter_period,
            request_params=request_params
        )

    def shapes(self, shape: enums.ShapeType) -> list[models.Shape]:
        """
        https://geofred.stlouisfed.org/docs/api/geofred/shapes.html

        ## Description
        This request returns shape files from GeoFRED in Well-known text (WKT) format.

        ## API Request (HTTPS GET)
        https://api.stlouisfed.org/geofred/shapes/file?shape=bea&api_key=abcdefghijklmnopqrstuvwxyz123456

        ## API Response
        ```json
        {
          "bea": [
            {
              "name": "Far West",
              "code": "8",
              "centroid": "POINT(-142.362948378432 57.1478734829085)",
              "geometry": "MULTIPOLYGON(((-155.778234 20.245743,-155.772734 ...)))",
              "report name": "North Adams, MA-VT"
            }
            ...
          ]
        }
        ```

        ## Returns
        `List[pystlouisfed.models.Shape]`

        ## Example
        ```python
            import matplotlib.pyplot as plt
            from descartes import PolygonPatch
            from pystlouisfed.client import GeoFRED, ShapeType

            plt.figure()
            ax = plt.axes()
            geo_fred = GeoFRED(api_key='abcdefghijklmnopqrstuvwxyz123456')

            for country_shape in geo_fred.shapes(shape=ShapeType.country):
                ax.add_patch(PolygonPatch(country_shape.geometry, ec='#999999', fc='#6699cc', alpha=0.5, zorder=2))
            ax.axis('scaled')
            plt.show()
        ```
        .. image:: geofred_shape_map.png
        """  # noinspection

        wkt_list = self._client.get(
            "/geofred/shapes/file",
            shape.value,
            shape=shape
        )

        # replace whitespaces in dict keys
        for wkt in wkt_list:
            for key in list(wkt.keys()):
                wkt[key.replace(" ", "_")] = wkt.pop(key)

        return list(map(lambda wkt: models.Shape(**wkt), wkt_list))

    def series_group(self, series_id: str) -> models.SeriesGroup:
        """
        https://geofred.stlouisfed.org/docs/api/geofred/series_group.html

        ## Description
        This request returns the meta information needed to make requests for GeoFRED data.
        Minimum and maximum date are also supplied for the data range available.

        ## API Request (HTTPS GET)
        https://api.stlouisfed.org/geofred/series/group?series_id=SMU56000000500000001a&api_key=abcdefghijklmnopqrstuvwxyz123456

        ## API Response
        ```json
        {
          "series_group": [
            {
              "title": "All Employees: Total Private",
              "geom_type": "state",
              "group_id": "192",
              "season": "NSA",
              "units": "Thousands of Persons",
              "frequency": "m",
              "min_start_date": "1990-01-01",
              "max_start_date": "2015-06-01"
            }
          ]
        }
        ```

        ## Returns
        `models.SeriesGroup`

        ## Example
        ```python
            >>> geo_fred = GeoFRED(api_key='abcdefghijklmnopqrstuvwxyz123456')
            >>> print(geo_fred.series_group(series_id='SMU56000000500000001a'))
            SeriesGroup(title='All Employees: Total Private', region_type='state', series_group='1223', season='NSA', units='Thousands of Persons', frequency='a', min_date=datetime.date(1990, 1, 1), max_date=datetime.date(2020, 1, 1))
        ```
        """  # noinspection

        data = self._client.get(
            "/geofred/series/group",
            "series_group",
            series_id=series_id
        )

        return models.SeriesGroup(**data[0])

    def series_data(self, series_id: str, date: Optional[dt_date] = None, start_date: Optional[dt_date] = None) -> pd.DataFrame:
        """
        ## Parameters

        `series_id`
        The FRED series_id you want to request GeoFRED data for. Not all series that are in FRED have geographical data.

        `date`
        The date you want to request series group data from.

        `start_date`
        The start date you want to request series group data from. This allows you to pull a range of data

        ## Description
        https://geofred.stlouisfed.org/docs/api/geofred/series_data.html

        This request returns a cross section of regional data for a specified release dt_date.
        If no date is specified, the most recent data available are returned.

        ## API Request (HTTPS GET)
        https://api.stlouisfed.org/geofred/series/data?series_id=WIPCPI&api_key=abcdefghijklmnopqrstuvwxyz123456&date=2012-01-01

        ## API Response
        ```json
        {
          "meta": {
            "title": "Per Capita Personal Income by State (Dollars)",
            "region": "state",
            "seasonality": "Not Seasonally Adjusted",
            "units": "Dollars",
            "frequency": "Annual",
            "date": "2012-01-01",
            "data": {
              "2022-01-01": [
                {
                  "region": "Alabama",
                  "code": "01",
                  "value": "50637",
                  "series_id": "ALPCPI"
                },
              ...
            ]
          }
        }
        ```

        ## Returns
        `pandas.DataFrame`

        ## Example (`pandas.DataFrame`)
        ```python
        >>> geo_fred = GeoFRED(api_key='abcdefghijklmnopqrstuvwxyz123456')
        >>> geo_fred.series_data(series_id='WIPCPI')
              region  code  value series_id       year
        0  Louisiana    22  54622    LAPCPI 2022-01-01
        1     Nevada    32  61282    NVPCPI 2022-01-01
        2   Maryland    24  70730    MDPCPI 2022-01-01
        3    Arizona     4  56667    AZPCPI 2022-01-01
        4   New York    36  78089    NYPCPI 2022-01-01
        ```
        """  # noinspection

        if date is None:
            date = dt_date.today()

        if start_date is None:
            start_date = dt_date.today()

        years = self._client.get(
            "/geofred/series/data",
            "meta.data",
            series_id=series_id,
            date=date,
            start_date=start_date
        )

        df = pd.DataFrame(
            self._add_years(years[0])
        )

        if not df.empty:
            df.value = df.value.replace(self.EMPTY_VALUE, np.nan)
            df["year"] = pd.to_datetime(df["year"], format="%Y-%m-%d")

            df = df.astype(dtype={
                "value": int,
                "series_id": "category",
                "region": "category",
                "code": int
            })

        return df

    def regional_data(
            self,
            series_group: str,
            region_type: enums.RegionType,
            date: dt_date,
            season: enums.Seasonality,
            units: str = "Dollars",  # Documentation is missing
            start_date: Optional[dt_date] = None,
            frequency: Optional[enums.Frequency] = None,
            transformation: enums.Unit = enums.Unit.lin,
            aggregation_method: enums.AggregationMethod = enums.AggregationMethod.average
    ) -> pd.DataFrame:
        """
        ## Parameters

        `series_group`
        The ID for a group of seriess found in GeoFRED.

        `region_type`
        The region you want want to pull data for.

        `date
        The date you want to pull a series group data from.

        `start_date`
        The start date you want to request series group data from.
        This allows you to pull a range of data

        `units`
        The units of the series you want to pull.

        `season`
        The seasonality of the series group.

        `frequency`
        An optional parameter that indicates a lower frequency to aggregate values to.
        The GeoFRED frequency aggregation feature converts higher frequency data series into lower frequency data series (e.g. converts a monthly data series into an annual data series).
        In GeoFRED, the highest frequency data is daily, and the lowest frequency data is annual.
        There are 3 aggregation methods available- average, sum, and end of period.
        See the aggregation_method parameter.

        `transformation`
        A key that indicates a data value transformation.

        ## Description
        https://geofred.stlouisfed.org/docs/api/geofred/regional_data.html

        This request returns a cross section of regional data

        ## API Request (HTTPS GET)
        https://api.stlouisfed.org/geofred/regional/data?api_key=abcdefghijklmnopqrstuvwxyz123456&series_group=882&date=2013-01-01&region_type=state&units=Dollars&frequency=a&season=NSA
        ## API Response
        ```json
        {
          "meta": {
            "title": "Per Capita Personal Income by State (Dollars)",
            "region": "state",
            "seasonality": "Not Seasonally Adjusted",
            "units": "Dollars",
            "frequency": "Annual",
            "data": {
              "2013-01-01": [
                {
                  "region": "Alabama",
                  "code": "01",
                  "value": "36014",
                  "series_id": "ALPCPI"
                },
                ...
                ]
            }
          }
        }
        ```

        ## Returns
        `pandas.DataFrame`

        ## Example (`pandas.DataFrame`)
        ```python
        >>> geo_fred = GeoFRED(api_key='abcdefghijklmnopqrstuvwxyz123456')
        >>> geo_fred.regional_data(series_group='882', date=date(2013, 1, 1), region_type=RegionType.state, frequency=Frequency.anual, season=Seasonality.not_seasonally_adjusted)
                         region  code  value series_id       year
        0                Hawaii    15  43931    HIPCPI 2013-01-01
        1            California     6  48502    CAPCPI 2013-01-01
        2  District of Columbia    11  67774    DCPCPI 2013-01-01
        3              Colorado     8  47404    COPCPI 2013-01-01
        4           Connecticut     9  62647    CTPCPI 2013-01-01
        ```
        """  # noinspection

        if start_date is None:
            start_date = dt_date.today()

        if frequency is not None and frequency not in enums.Frequency:
            raise ValueError(f'Variable frequency is not one of the values: {", ".join(map(str, enums.Frequency))}')

        if aggregation_method not in enums.AggregationMethod:
            raise ValueError(f'Variable aggregation_method is not one of the values: {", ".join(map(str, enums.AggregationMethod))}')

        if transformation not in enums.Unit:
            raise ValueError(f'Variable transformation is not one of the values: {", ".join(map(str, enums.Unit))}')

        years = self._client.get(
            "/geofred/regional/data",
            "meta.data",
            series_group=series_group,
            region_type=region_type,
            date=date,
            units=units,
            season=season,
            start_date=start_date,
            frequency=frequency,
            transformation=transformation,
            aggregation_method=aggregation_method
        )

        df = pd.DataFrame(
            self._add_years(years[0])
        )

        if not df.empty:
            df.value = df.value.replace(self.EMPTY_VALUE, np.nan)
            df["year"] = pd.to_datetime(df["year"], format="%Y-%m-%d")

            df = df.astype(dtype={
                "value": int,
                "series_id": "category",
                "region": "category",
                "code": int
            })

        return df

    def _add_years(self, data: dict) -> Generator[dict, None, None]:
        """
        transform dict indexed by year from:
        ```json
        {
          "2020-01-01": [
            {
              "region": "Alabama",
              "code": "01",
              "value": "46479",
              "series_id": "ALPCPI"
            },
            ...
          ]
        }
        ```
        to
        ```json
        [
          {
            "region": "Alabama",
            "code": "01",
            "value": "46479",
            "series_id": "ALPCPI",
            "year": "2020-01-01"
          },
          ...
        ]
        ```
        """  # noinspection
        for year, rows in data.items():
            for row in rows:
                row["year"] = year
                yield row
