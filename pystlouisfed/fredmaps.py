import logging
from collections.abc import Generator
from datetime import date as dt_date
from datetime import timedelta
from typing import NoReturn
from typing import Optional

import numpy as np
import pandas as pd
from geopandas import GeoDataFrame

from pystlouisfed import enums
from pystlouisfed import models
from .client import Client

logger = logging.getLogger(__name__)


class FREDMaps:
    """
    | https://fredaccount.stlouisfed.org/public/dashboard/83217
    | Maps provide a cross-sectional perspective that lets you compare regions on a map while complementing and expanding the data analysis you get on a time-series graph. 
    
    FRED has 9 types (:class:`pystlouisfed.enums.ShapeType`) of maps: 
    
    #. U.S. counties
    #. U.S. metro areas
    #. U.S. states
    #. nations
    #. Federal Reserve Districts
    #. Census regions
    #. Census divisions
    #. BEA regions 
    #. NECTAs (New England city and town areas)
    
    :param api_key: 32 character alpha-numeric lowercase string
    :type api_key: str
    :type ratelimiter_enabled: bool
    :type ratelimiter_max_calls: int
    :type ratelimiter_period: int
    :param request_params: HTTP GET method parameters, see https://docs.python-requests.org/en/latest/api/#requests.request
    :type request_params: dict
    """  # noqa

    EMPTY_VALUE = "."

    def __init__(
            self,
            api_key: str,
            ratelimiter_enabled: bool = False,
            ratelimiter_max_calls: int = 120,
            ratelimiter_period: timedelta = timedelta(seconds=60),
            request_params: Optional[dict] = None
    ) -> NoReturn:

        if api_key is None or len(api_key) != 32:
            raise ValueError("Variable api_key must be 32 character length alphanumeric string.")

        self._client = Client(
            key=api_key.lower(),
            ratelimiter_enabled=ratelimiter_enabled,
            ratelimiter_max_calls=ratelimiter_max_calls,
            ratelimiter_period=ratelimiter_period,
            request_params=request_params
        )

    def shapes(self, shape: enums.ShapeType) -> GeoDataFrame:
        """
        :param shape: Shape
        :type shape: enums.ShapeType
        :rtype: geopandas.GeoDataFrame

        Description
        -----------
        | https://fred.stlouisfed.org/docs/api/geofred/shapes.html
        | This request returns shape files from FRED in GeoJSON format.

        IGNORE:
        API Request (HTTPS GET)
        -----------------------
        https://api.stlouisfed.org/geofred/shapes/file?shape=country&api_key=abcdefghijklmnopqrstuvwxyz123456

        API Response
        ------------
        .. code-block:: json
           
            {
                "title": "World, Miller projection, medium resolution",
                "version": "1.1.3",
                "type": "FeatureCollection",
                "copyright": "Copyright (c) 2020 Highsoft AS, Based on data from Natural Earth",
                "copyrightShort": "Natural Earth",
                "copyrightUrl": "http://www.naturalearthdata.com",
                "crs": {
                    "type": "name",
                    "properties": {
                        "name": "urn:ogc:def:crs:EPSG:54003"
                    }
                },
                "hc-transform": {
                    "default": {
                        "crs": "+proj=mill +lat_0=0 +lon_0=0 +x_0=0 +y_0=0 +R_A +datum=WGS84 +units=m +no_defs",
                        "scale": 0.0000172182781654,
                        "jsonres": 15.5,
                        "jsonmarginX": -999,
                        "jsonmarginY": 9851,
                        "xoffset": -19495356.3693,
                        "yoffset": 12635908.1982
                    }
                },
                "features": [
                    {
                        "type": "Feature",
                        "id": "FO",
                        "properties": {
                            "hc-group": "admin0",
                            "hc-middle-x": 0.48,
                            "hc-middle-y": 0.54,
                            "hc-key": "fo",
                            "hc_a2": "FO",
                            "name": "Faroe Islands",
                            "labelrank": "6",
                            "country-abbrev": "Faeroe Is.",
                            "subregion": "Northern Europe",
                            "region-wb": "Europe & Central Asia",
                            "iso-a3": "FRO",
                            "iso-a2": "FO",
                            "woe-id": "23424816",
                            "continent": "Europe"
                        },
                        "geometry": {
                        "type": "Polygon",
                        "coordinates": [
                            [
                                [ 3991, 8611 ],
                                [ 4005, 8598 ],
                                [ 4004, 8594 ],
                                [ 3989, 8605 ],
                                [ 3991, 8611 ]
                            ]
                        ]
                    }
                ]
            }
        IGNORE
        
        Examples
        --------
        
        Get country polygons:
            
        .. code-block:: python

            from pystlouisfed import FREDMaps, ShapeType
            
            fred_maps = FREDMaps(api_key="abcdefghijklmnopqrstuvwxyz123456")
            shapes = fred_maps.shapes(shape=ShapeType.country)
            
            #                                                       geometry hc-group  hc-middle-x  hc-middle-y hc-key hc_a2                                  name labelrank country-abbrev                  subregion                   region-wb iso-a3 iso-a2    woe-id                continent
            # 0    POLYGON ((3991.000 8611.000, 4005.000 8598.000...   admin0         0.48         0.54     fo    FO                         Faroe Islands         6     Faeroe Is.            Northern Europe       Europe & Central Asia    FRO     FO  23424816                   Europe
            # 1    POLYGON ((-605.000 6652.000, -606.000 6652.000...   admin0         0.57         0.58     um    UM  United States Minor Outlying Islands         5       U.S. MOI    Seven seas (open ocean)         East Asia & Pacific    UMI     UM  28289407            North America
            # 2    MULTIPOLYGON (((556.000 8034.000, 559.000 8032...   admin0         0.68         0.68     us    US              United States of America         2         U.S.A.           Northern America               North America    USA     US  23424977            North America
            # 3    MULTIPOLYGON (((8389.000 7914.000, 8390.000 79...   admin0         0.52         0.66     jp    JP                                 Japan         2          Japan               Eastern Asia         East Asia & Pacific    JPN     JP  23424856                     Asia
            # 4    POLYGON ((5849.000 6344.000, 5852.000 6341.000...   admin0         0.58         0.41     sc    SC                            Seychelles         6           Syc.             Eastern Africa          Sub-Saharan Africa    SYC     SC  23424941  Seven seas (open ocean)
            # 5    MULTIPOLYGON (((6818.000 7133.000, 6820.000 71...   admin0         0.34         0.43     in    IN                                 India         2          India              Southern Asia                  South Asia    IND     IN  23424848                     Asia

        Plot with `Matplotlib <https://matplotlib.org/>`_:
        
        .. code-block:: python
        
            from pystlouisfed import FREDMaps, ShapeType
            import matplotlib.pyplot as plt
            
            gdf = FREDMaps(api_key="abcdefghijklmnopqrstuvwxyz123456") \\
                    .shapes(shape=ShapeType.state) \\
                    .plot(figsize=(12, 8))
                    
            plt.show()

        .. image:: maps_states_plt.png

        Plot with `Plotly <https://plotly.com/python/>`_:
        
        .. code-block:: python

            from pystlouisfed import FREDMaps, ShapeType
            import plotly.express as px
            
            gdf = FREDMaps(api_key="abcdefghijklmnopqrstuvwxyz123456") \\
                    .shapes(shape=ShapeType.state) \\
                    .to_crs(epsg=4326) \\
                    .set_index("name")
            
            fig = px.choropleth(
                gdf,
                geojson=gdf.geometry,
                locations=gdf.index,
                color="fips",
            )
            
            fig.update_layout(width=1200, height=1000, showlegend=False)
            fig.update_geos(fitbounds="locations", visible=False)
            fig.show()
        
        .. image:: maps_states.png
        
        or plot :py:class:`pystlouisfed.ShapeType.country`
        
        .. image:: maps_country.png
        
        """  # noqa

        feature_collection = self._client.get(
            endpoint="/geofred/shapes/file",
            shape=shape
        )

        # FRED use wrong data source - "urn:ogc:def:crs:EPSG:54003"
        # 54003 is ESRI and not EPSG - https://epsg.io/54003
        # as alternative we use hc-transform PROJ4 value
        if "hc-transform" in feature_collection:
            crs = feature_collection["hc-transform"]["default"]["crs"]
        else:
            crs = feature_collection["crs"]["properties"]["name"]

        return GeoDataFrame.from_features(
            features=feature_collection,
            crs=crs
        )

    def series_group(self, series_id: str) -> models.SeriesGroup:
        """
        :param series_id: Series ID
        :type series_id: str
        :rtype: models.SeriesGroup

        Description
        -----------
        | https://fred.stlouisfed.org/docs/api/geofred/series_group.html
        | This request returns the meta information needed to make requests for FRED data.
        | Minimum and maximum date are also supplied for the data range available.

        IGNORE:
        API Request (HTTPS GET)
        -----------------------
        https://api.stlouisfed.org/geofred/series/group?series_id=SMU56000000500000001a&api_key=abcdefghijklmnopqrstuvwxyz123456

        API Response
        ------------
        .. code-block:: json

            {
                "series_group":
                    {
                        "title": "All Employees: Total Private",
                        "region_type": "state",
                        "series_group": "1223",
                        "season": "NSA",
                        "units": "Thousands of Persons",
                        "frequency": "Annual",
                        "min_date": "1990-01-01",
                        "max_date": "2021-01-01"
                    }
            }
        IGNORE
        
        Example
        -------
        .. code-block:: python

            fred_maps = FREDMaps(api_key="abcdefghijklmnopqrstuvwxyz123456")
            group = geo_fred.series_group(series_id="SMU56000000500000001a")
           
            # SeriesGroup(title='All Employees: Total Private', region_type='state', series_group='1223', season='NSA', units='Thousands of Persons', frequency='a', min_date=datetime.date(1990, 1, 1), max_date=datetime.date(2020, 1, 1))
        """  # noqa

        data = self._client.get(
            endpoint="/geofred/series/group",
            list_key="series_group",
            series_id=series_id
        )

        return models.SeriesGroup(**data)

    def series_data(
            self,
            series_id: str,
            date: Optional[dt_date] = None,
            start_date: Optional[dt_date] = None
    ) -> pd.DataFrame:
        """
        :param series_id: The FRED series_id you want to request maps data for. Not all series that are in FRED have geographical data.
        :type series_id: str
        :param date: The date you want to request series group data from.
        :type date: datetime.date
        :param start_date: The start date you want to request series group data from. This allows you to pull a range of data.
        :type start_date: datetime.date
        :rtype: pandas.DataFrame

        Description
        -----------
        | https://fred.stlouisfed.org/docs/api/geofred/series_data.html
        | This request returns a cross section of regional data for a specified release date
        | If no date is specified, the most recent data available are returned.

        IGNORE:
        API Request (HTTPS GET)
        -----------------------
        https://api.stlouisfed.org/geofred/series/data?series_id=WIPCPI&api_key=abcdefghijklmnopqrstuvwxyz123456&date=2012-01-01

        API Response
        ------------
        .. code-block:: json

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
               ]
             }
           }
        IGNORE
        
        Example
        -------
        .. code-block:: python 

           fred_maps = FREDMaps(api_key="abcdefghijklmnopqrstuvwxyz123456")
           fred_maps.series_data(series_id='WIPCPI')

           #       region  code  value series_id       year
           # 0  Louisiana    22  54622    LAPCPI 2022-01-01
           # 1     Nevada    32  61282    NVPCPI 2022-01-01
           # 2   Maryland    24  70730    MDPCPI 2022-01-01
           # 3    Arizona     4  56667    AZPCPI 2022-01-01
           # 4   New York    36  78089    NYPCPI 2022-01-01
        """  # noqa

        years = self._client.get(
            "/geofred/series/data",
            "meta.data",
            series_id=series_id,
            date=date,
            start_date=start_date
        )

        if years is None:
            df = pd.DataFrame()
        else:
            df = pd.DataFrame(
                self._add_years(years)
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
        :param series_group: The ID for a group of seriess found in FRED.
        :type series_group: str
        :param region_type: The region you want want to pull data for.
        :type region_type: enums.RegionType
        :param date: The date you want to pull a series group data from.
        :type date: datetime.date
        :param season: The seasonality of the series group.
        :type season: enums.Seasonality
        :param units: The units of the series you want to pull.
        :type units: str
        :param start_date: The start date you want to request series group data from. This allows you to pull a range of data.
        :type start_date: datetime.date
        :param frequency: Frequency automatically assigns the default frequency of the map when using the Request Wizard above. The parameter can be used as a frequency aggregation feature. The maps frequency aggregation feature converts higher frequency data series into lower frequency data series (e.g. converts a monthly data series into an annual data series). In maps, the highest frequency data is daily, and the lowest frequency data is annual. There are 3 aggregation methods available- average, sum, and end of period. See the aggregation_method parameter.
        :type frequency: enums.Frequency
        :param transformation: A key that indicates a data value transformation.
        :type transformation: enums.Unit
        :param aggregation_method: One of the following values: 'avg', 'sum', 'eop'
        :type aggregation_method: enums.AggregationMethod
        :rtype: pandas.DataFrame

        Description
        -----------
        | https://fred.stlouisfed.org/docs/api/geofred/regional_data.html
        | This request returns a cross section of regional data.

        IGNORE:
        API Request (HTTPS GET)
        -----------------------
        https://api.stlouisfed.org/geofred/regional/data?api_key=abcdefghijklmnopqrstuvwxyz123456&series_group=882&date=2013-01-01&region_type=state&units=Dollars&frequency=a&season=NSA

        API Response
        ------------
        .. code-block:: json 

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
                 ]
               }
             }
           }
        IGNORE
        
        Example
        -------
        .. code-block:: python 

           fred_maps = FREDMaps(api_key="abcdefghijklmnopqrstuvwxyz123456")
           fred_maps.regional_data(
                series_group='882',
                date=date(2013, 1, 1),
                start_date=datetime.date(2014, 1, 1),
                region_type=RegionType.state,
                frequency=Frequency.anual,
                season=Seasonality.not_seasonally_adjusted
            )

            #                    region  code  value series_id       year
            # 0                   Texas    48  46739    TXPCPI 2014-01-01
            # 1             Mississippi    28  34624    MSPCPI 2014-01-01
            # 2                  Hawaii    15  45448    HIPCPI 2014-01-01
            # 3                Kentucky    21  37226    KYPCPI 2014-01-01
            # ...
        """  # noqa

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

        if years is None:
            df = pd.DataFrame()
        else:
            df = pd.DataFrame(
                self._add_years(years)
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

        .. code-block:: json 

           {
             "2020-01-01": [
               {
                 "region": "Alabama",
                 "code": "01",
                 "value": "46479",
                 "series_id": "ALPCPI"
               },
             ]
           }

        to

        .. code-block:: json 

            [
              {
                "region": "Alabama",
                "code": "01",
                "value": "46479",
                "series_id": "ALPCPI",
                "year": "2020-01-01"
              },
            ]
        """  # noqa
        for year, rows in data.items():
            for row in rows:
                row["year"] = year
                yield row
