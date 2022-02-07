import logging
import xml.etree.ElementTree as ET
from contextlib import nullcontext
from datetime import datetime, date, timedelta
from enum import Enum
from functools import reduce
from typing import List, Generator

import numpy as np
import pandas as pd
import requests
import sickle
from ratelimiter import RateLimiter

import pystlouisfed.enums as enums
import pystlouisfed.models as models

logger = logging.getLogger(__name__)


class URLFactory:
    SEPARATOR = ';'

    def __init__(self, key: str, base: str = 'https://api.stlouisfed.org'):
        self._base = base
        self._params = {
            'api_key': key,
            'file_type': 'json'
        }

    def create(self, endpoint: str, params: dict) -> str:

        # remove None values
        filtered = {k: v for k, v in params.items() if v is not None}

        for k, v in filtered.items():

            if isinstance(v, Enum):
                filtered[k] = v.value

            if isinstance(v, list):
                filtered[k] = self.SEPARATOR.join(v)

            if isinstance(v, bool):
                filtered[k] = str(v).lower()

            # YYYYMMDDHhmm formatted string
            # Example: 2018-03-02 2:20 would be 201803020220
            if isinstance(v, datetime):
                filtered[k] = v.strftime('%Y%m%d%H%M')

            # replace whitespaces with +
            if isinstance(filtered[k], str):
                filtered[k] = filtered[k].replace(' ', '+')

        payload_str = "&".join("%s=%s" % (k, v) for k, v in {**self._params, **filtered}.items())

        url = '{}{}?{}'.format(self._base, endpoint, payload_str)
        logger.debug('URL: {}'.format(url))

        return url


class Client:
    rate_limit: int

    _rate_limit_remaining: int
    _rate_limit_last_check: datetime
    _rate_limiter: RateLimiter
    _rate_limiter_enabled: bool
    _headers: dict = {
        "Accept": "application/json",
        "Accept-Encoding": 'gzip',
        "Cache-Control": "no-cache",
        "User-Agent": "Python FRED Client"
    }
    _url: URLFactory

    def __init__(self, key: str, ratelimiter_enabled: bool, ratelimiter_max_calls: int, ratelimiter_period: int):
        self._url = URLFactory(key)
        self.rate_limit = 120
        self._rate_limit_remaining = None
        self._rate_limit_last_check = None

        if ratelimiter_enabled:
            self._rate_limiter = RateLimiter(max_calls=ratelimiter_max_calls, period=ratelimiter_period)
        else:
            self._rate_limiter = nullcontext()

    @property
    def rate_limit_remaining(self) -> int:
        return self.rate_limit if self._rate_limit_last_check is None or self._rate_limit_last_check <= (datetime.now() - timedelta(seconds=60)) else self._rate_limit_remaining

    def get(self, endpoint: str, list_key: str, limit: int = None, **kwargs) -> list:

        offset = 0 if limit is not None else None
        stop = False
        result = list()
        request_number = 1

        while not stop:

            url = self._url.create(
                endpoint, {
                    **kwargs,
                    **{
                        'limit': limit,
                        'offset': offset
                    }
                }
            )

            with self._rate_limiter:

                res = requests.get(url, headers=self._headers)

                # GeoFRED return error codes and messages in XML
                if res.headers.get('content-type').startswith('text/xml') and res.status_code != 200:
                    element = ET.fromstring(res.content.decode())
                    raise Exception('Received error code: "{}" and message: "{}" for URL {}'.format(element.get('code'), element.get('message'), url))

                elif not res.headers.get('content-type').startswith('application/json'):
                    raise Exception('Unexpected content-type "{}" for URL {}'.format(res.headers.get('content-type'), url))

                data = res.json()

                if res.status_code in [400, 403, 420, 429, 500]:
                    raise Exception('Received error code: "{}" and message: "{}" for URL {}'.format(data['error_code'], " ".join(data['error_message'].split()), url))
                elif res.status_code != 200:
                    raise Exception('Received status code: "{}" for URL {}'.format(res.status_code, url))

                self.rate_limit = int(res.headers['x-rate-limit-limit'])
                self._rate_limit_remaining = int(res.headers['x-rate-limit-remaining'])
                self._rate_limit_last_check = datetime.now()
                logger.debug("Api rate limit: {} out of {} requests per minute remaining".format(self.rate_limit_remaining, self.rate_limit))

                list_data = self._deep_get(data, list_key)

                if 'count' not in data:
                    # GeoFRED.series_data and GeoFRED.regional_data return dict of years
                    return list_data if isinstance(list_data, list) else [list_data]
                else:
                    number_of_requests = int(data['count'] / limit) + 1 if limit is not None else 1
                    logger.debug("Number of records: {}, Request {} of {}".format(data['count'], request_number, number_of_requests))

                if limit is None or data['count'] < limit or len(list_data) < limit:
                    stop = True

                if len(list_data) == limit:
                    offset += limit

                result += list_data
                request_number += 1

        return result

    def _deep_get(self, dictionary: dict, keys: str, default=None):
        return reduce(lambda d, key: d.get(key, default) if isinstance(d, dict) else default, keys.split("."), dictionary)


class FRED:
    """
    The FRED API is a web service that allows developers to write programs and build applications that retrieve economic data from the FRED and ALFRED websites hosted by the Economic Research Division of the Federal Reserve Bank of St. Louis.
    Requests can be customized according to data source, release, category, series, and other preferences.

    https://fred.stlouisfed.org

    https://fred.stlouisfed.org/docs/api/fred/
    """
    EMPTY_VALUE = '.'

    def __init__(self, api_key: str, ratelimiter_enabled: bool = True, ratelimiter_max_calls: int = 2, ratelimiter_period: int = 1):

        if api_key is None:
            raise Exception('Variable api_key is not set.')

        self._client = Client(key=api_key, ratelimiter_enabled=ratelimiter_enabled, ratelimiter_max_calls=ratelimiter_max_calls, ratelimiter_period=ratelimiter_period)

    @property
    def rate_limit(self) -> int:
        return self._client.rate_limit

    @property
    def rate_limit_remaining(self) -> int:
        return self._client.rate_limit_remaining

    """
    Category

    https://fred.stlouisfed.org/categories
    """

    def category(self, category_id: int = 0) -> models.Category:
        """
        ## Parameters

        `category_id`
        The id for a category.

        ## Description
        https://fred.stlouisfed.org/docs/api/fred/category.html

        Get a category.

        ## API Request (HTTPS GET)
        https://api.stlouisfed.org/fred/category?category_id=125&api_key=abcdefghijklmnopqrstuvwxyz123456&file_type=json

        ## API Response
        ```json
        {
            "categories": [
                {
                    "id": 125,
                    "name": "Trade Balance",
                    "parent_id": 13
                }
            ]
        }
        ```

        ## Returns
        `pystlouisfed.models.Category`

        ## Example
        ```python
        >>> fred = FRED(api_key='abcdefghijklmnopqrstuvwxyz123456')
        >>> fred.category(category_id=125)
            Category(id=125, name='Trade Balance', parent_id=13)
        ```
        """

        if int(category_id) < 0:
            raise ValueError('Variable category_id is not 0 or a positive integer.')

        data = self._client.get(
            '/fred/category',
            'categories',
            category_id=category_id
        )

        return models.Category(**data[0])

    def category_children(self, category_id: int = 0, realtime_start: date = None, realtime_end: date = None) -> pd.DataFrame:
        """
        ## Parameters

        `category_id`
        The id for a category.

        `realtime_start`
        The start of the real-time period. For more information, see [Real-Time Periods](https://fred.stlouisfed.org/docs/api/fred/realtime_period.html).

        `realtime_end`
        The end of the real-time period. For more information, see [Real-Time Periods](https://fred.stlouisfed.org/docs/api/fred/realtime_period.html).

        ## Description
        https://fred.stlouisfed.org/docs/api/fred/category_children.html

        Get the child categories for a specified parent category.

        ## API Request (HTTPS GET)
        https://api.stlouisfed.org/fred/category/children?category_id=13&api_key=abcdefghijklmnopqrstuvwxyz123456&file_type=json

        ## API Response
        ```json
        {
            "categories": [
                {
                    "id": 16,
                    "name": "Exports",
                    "parent_id": 13
                },
                ...
            ]
        }
        ```

        ## Returns
        `pandas.DataFrame`

        ## Example
        ```python
        >>> fred = FRED(api_key='abcdefghijklmnopqrstuvwxyz123456')
        >>> fred.category_children(category_id=13).head()
                                                name  parent_id
            id
            16                               Exports         13
            17                               Imports         13
            3000          Income Payments & Receipts         13
            33705  International Investment Position         13
            125                        Trade Balance         13
        ```
        """

        if realtime_start is not None and realtime_start < date(1776, 7, 4):
            raise ValueError('Variable realtime_start ("{}") is before min date 1776-07-04.'.format(realtime_start))

        if realtime_start is not None and realtime_end is not None and realtime_start > realtime_end:
            raise ValueError('The date set by variable realtime_start ("{}") can not be after the date set by variable realtime_end ("{}").'.format(realtime_start, realtime_end))

        data = self._client.get(
            '/fred/category/children',
            'categories',
            category_id=category_id,
            realtime_start=realtime_start,
            realtime_end=realtime_end
        )

        return pd.DataFrame(data).astype(dtype={
            'name': 'string'
        }).set_index('id')

    def category_related(self, category_id: int = 0, realtime_start: date = None, realtime_end: date = None) -> pd.DataFrame:

        """
        ## Parameters

        `category_id`
        The id for a category.

        `realtime_start`
        The start of the real-time period. For more information, see [Real-Time Periods](https://fred.stlouisfed.org/docs/api/fred/realtime_period.html).

        `realtime_end`
        The end of the real-time period. For more information, see [Real-Time Periods](https://fred.stlouisfed.org/docs/api/fred/realtime_period.html).

        ## Description
        https://fred.stlouisfed.org/docs/api/fred/category_related.html

        Get the related categories for a category.
        A related category is a one-way relation between 2 categories that is not part of a parent-child category hierarchy.
        Most categories do not have related categories.


        ## API Request (HTTPS GET)
        https://api.stlouisfed.org/fred/category/related?category_id=32073&api_key=abcdefghijklmnopqrstuvwxyz123456&file_type=json

        ## API Response
        ```json
        {
            "categories": [
                {
                    "id": 149,
                    "name": "Arkansas",
                    "parent_id": 27281
                },
                ...
            ]
        }
        ```

        ## Returns
        `pandas.DataFrame`

        ## Example
        ```python
        >>> fred = FRED(api_key='abcdefghijklmnopqrstuvwxyz123456')
        >>> fred.category_related(category_id=32073).head()
                        name  parent_id
            id
            149     Arkansas      27281
            150     Illinois      27281
            151      Indiana      27281
            152     Kentucky      27281
            153  Mississippi      27281
        ```
        """

        if realtime_start is not None and realtime_start < date(1776, 7, 4):
            raise ValueError('Variable realtime_start ("{}") is before min date 1776-07-04.'.format(realtime_start))

        if realtime_start is not None and realtime_end is not None and realtime_start > realtime_end:
            raise ValueError('The date set by variable realtime_start ("{}") can not be after the date set by variable realtime_end ("{}").'.format(realtime_start, realtime_end))

        data = self._client.get(
            '/fred/category/related',
            'categories',
            category_id=category_id,
            realtime_start=realtime_start,
            realtime_end=realtime_end
        )

        return pd.DataFrame(data).astype(dtype={
            'name': 'string'
        }).set_index('id')

    def category_series(
            self,
            category_id: int = 0,
            realtime_start: date = None,
            realtime_end: date = None,
            order_by: enums.OrderBy = enums.OrderBy.series_id,
            sort_order: enums.SortOrder = enums.SortOrder.asc,
            filter_variable: enums.FilterVariable = None,
            filter_value: enums.FilterValue = None,
            tag_names: List[str] = None,
            exclude_tag_names: List[str] = None
    ) -> pd.DataFrame:
        """
        ## Parameters

        `category_id`
        The id for a category.

        `realtime_start`
        The start of the real-time period. For more information, see [Real-Time Periods](https://fred.stlouisfed.org/docs/api/fred/realtime_period.html).

        `realtime_end`
        The end of the real-time period. For more information, see [Real-Time Periods](https://fred.stlouisfed.org/docs/api/fred/realtime_period.html).

        `order_by`
        Order results by values of the specified attribute.

        `sort_order`
        Sort results is ascending or descending order for attribute values specified by order_by.

        `filter_variable`
        The attribute to filter results by.

        `filter_value`
        The value of the filter_variable attribute to filter results by.

        `tag_names`
        Tuple of tag names that series match all of.

        `exclude_tag_names`
        Tuple of tag names that series match none of.

        ## Description
        https://fred.stlouisfed.org/docs/api/fred/category_series.html

        Get the series in a category.

        ## API Request (HTTPS GET)
        https://api.stlouisfed.org/fred/category/series?category_id=125&api_key=abcdefghijklmnopqrstuvwxyz123456&file_type=json

        ## API Response
        ```json
        {
          "realtime_start": "2017-08-01",
          "realtime_end": "2017-08-01",
          "order_by": "series_id",
          "sort_order": "asc",
          "count": 45,
          "offset": 0,
          "limit": 1000,
          "seriess": [
            {
              "id": "BOPBCA",
              "realtime_start": "2017-08-01",
              "realtime_end": "2017-08-01",
              "title": "Balance on Current Account (DISCONTINUED)",
              "observation_start": "1960-01-01",
              "observation_end": "2014-01-01",
              "frequency": "Quarterly",
              "frequency_short": "Q",
              "units": "Billions of Dollars",
              "units_short": "Bil. of $",
              "seasonal_adjustment": "Seasonally Adjusted",
              "seasonal_adjustment_short": "SA",
              "last_updated": "2014-06-18 08:41:28-05",
              "popularity": 32,
              "group_popularity": 34,
              "notes": "This series has been discontinued as a result of the comprehensive restructuring of the international economic accounts (http://www.bea.gov/international/modern.htm).For a crosswalk of the old and new series in FRED see: http://research.stlouisfed.org/CompRevisionReleaseID49.xlsx."
            },
            ...
          ]
        }
        ```

        ## Returns
        `pandas.DataFrame`

        ## Example
        ```python
        >>> fred = FRED(api_key='abcdefghijklmnopqrstuvwxyz123456')
        >>> fred.category_series(category_id=125).head()
                    realtime_start realtime_end                                              title observation_start observation_end  frequency frequency_short                units units_short      seasonal_adjustment seasonal_adjustment_short              last_updated  popularity  group_popularity                                              notes
            id
            AITGCBN     2022-02-05   2022-02-05  Advance U.S. International Trade in Goods: Bal...        2021-12-01      2021-12-01    Monthly               M  Millions of Dollars   Mil. of $  Not Seasonally Adjusted                       NSA 2022-01-26 13:31:05+00:00           3                26  This advance estimate represents the current m...
            AITGCBS     2022-02-05   2022-02-05  Advance U.S. International Trade in Goods: Bal...        2021-12-01      2021-12-01    Monthly               M  Millions of Dollars   Mil. of $      Seasonally Adjusted                        SA 2022-01-26 13:31:02+00:00          26                26  This advance estimate represents the current m...
            BOPBCA      2022-02-05   2022-02-05          Balance on Current Account (DISCONTINUED)        1960-01-01      2014-01-01  Quarterly               Q  Billions of Dollars   Bil. of $      Seasonally Adjusted                        SA 2014-06-18 13:41:28+00:00          10                11  This series has been discontinued as a result ...
            BOPBCAA     2022-02-05   2022-02-05          Balance on Current Account (DISCONTINUED)        1960-01-01      2013-01-01     Annual               A  Billions of Dollars   Bil. of $  Not Seasonally Adjusted                       NSA 2014-06-18 13:41:28+00:00           2                11  This series has been discontinued as a result ...
            BOPBCAN     2022-02-05   2022-02-05          Balance on Current Account (DISCONTINUED)        1960-01-01      2014-01-01  Quarterly               Q  Billions of Dollars   Bil. of $  Not Seasonally Adjusted                       NSA 2014-06-18 13:41:28+00:00           1                11  This series has been discontinued as a result ...
        ```
        """

        allowed_orders = [
            enums.OrderBy.series_id,
            enums.OrderBy.title,
            enums.OrderBy.units,
            enums.OrderBy.frequency,
            enums.OrderBy.seasonal_adjustment,
            enums.OrderBy.realtime_start,
            enums.OrderBy.realtime_end,
            enums.OrderBy.last_updated,
            enums.OrderBy.observation_start,
            enums.OrderBy.observation_end,
            enums.OrderBy.popularity,
            enums.OrderBy.group_popularity
        ]

        if order_by not in allowed_orders:
            raise ValueError('Variable order_by ({}) is not one of the values: {}'.format(order_by, ', '.join(map(str, allowed_orders))))

        if filter_variable is not None and filter_variable not in enums.FilterVariable:
            raise ValueError('Variable filter_variable ({}) is not one of the values: {}'.format(filter_variable, ', '.join(map(str, enums.FilterVariable))))

        if exclude_tag_names is not None and tag_names is None:
            raise ValueError('Parameter exclude_tag_names requires that parameter tag_names also be set to limit the number of matching series.')

        if realtime_start is not None and realtime_start < date(1776, 7, 4):
            raise ValueError('Variable realtime_start ("{}") is before min date 1776-07-04.'.format(realtime_start))

        if realtime_start is not None and realtime_end is not None and realtime_start > realtime_end:
            raise ValueError('The date set by variable realtime_start ("{}") can not be after the date set by variable realtime_end ("{}").'.format(realtime_start, realtime_end))

        df = pd.DataFrame(
            self._client.get(
                '/fred/category/series',
                'seriess',
                limit=1000,
                category_id=category_id,
                realtime_start=realtime_start,
                realtime_end=realtime_end,
                order_by=order_by,
                sort_order=sort_order,
                filter_variable=filter_variable,
                filter_value=filter_value,
                tag_names=tag_names,
                exclude_tag_names=exclude_tag_names
            )
        )

        date_columns = [
            'realtime_start', 'realtime_end',
            'observation_start', 'observation_end',
        ]

        if not df.empty:
            df[date_columns] = df[date_columns].apply(pd.to_datetime, format='%Y-%m-%d')
            df.last_updated = pd.to_datetime(df.last_updated + '00', utc=True, format='%Y-%m-%d %H:%M:%S%z')

            df = df.astype(dtype={
                'id': 'string',
                'title': 'string',
                'notes': 'string',
                'seasonal_adjustment_short': 'category',
                'seasonal_adjustment': 'category',
                'units_short': 'category',
                'units': 'category',
                'frequency_short': 'category',
                'frequency': 'category'
            }).set_index('id')

        return df

    def category_tags(
            self,
            category_id: int = 0,
            realtime_start: date = None,
            realtime_end: date = None,
            tag_names: List[str] = None,
            tag_group_id: enums.TagGroupID = None,
            search_text: str = None,
            order_by: enums.OrderBy = enums.OrderBy.series_count,
            sort_order: enums.SortOrder = enums.SortOrder.asc
    ) -> pd.DataFrame:
        """
        ## Parameters

        `category_id`
        The id for a category.

        `realtime_start`
        The start of the real-time period. For more information, see [Real-Time Periods](https://fred.stlouisfed.org/docs/api/fred/realtime_period.html).

        `realtime_end`
        The end of the real-time period. For more information, see [Real-Time Periods](https://fred.stlouisfed.org/docs/api/fred/realtime_period.html).

        `tag_names`
        Tuple of tag names that series match all of.

        `tag_group_id`
        A tag group id to filter tags by type.

        `search_text`
        The words to find matching tags with.

        `order_by`
        Order results by values of the specified attribute.

        `sort_order`
        Sort results is ascending or descending order for attribute values specified by order_by.

        ## Description
        https://fred.stlouisfed.org/docs/api/fred/category_tags.html

        Get the FRED tags for a category.
        Optionally, filter results by tag name, tag group, or search. Series are assigned tags and categories.
        Indirectly through series, it is possible to get the tags for a category. No tags exist for a category that does not have series.
        See the related request fred/category/related_tags.

        ## API Request (HTTPS GET)
        https://api.stlouisfed.org/fred/category/tags?category_id=125&api_key=abcdefghijklmnopqrstuvwxyz123456&file_type=json

        ## API Response
        ```json
        {
            "realtime_start": "2013-08-13",
            "realtime_end": "2013-08-13",
            "order_by": "series_count",
            "sort_order": "desc",
            "count": 21,
            "offset": 0,
            "limit": 1000,
            "tags": [
                {
                    "name": "bea",
                    "group_id": "src",
                    "notes": "U.S. Department of Commerce: Bureau of Economic Analysis",
                    "created": "2012-02-27 10:18:19-06",
                    "popularity": 87,
                    "series_count": 24
                },
                ...
            ]
        }
        ```

        ## Returns
        `pandas.DataFrame`

        ## Example
        ```python
        >>> fred = FRED(api_key='abcdefghijklmnopqrstuvwxyz123456')
        >>> fred.category_tags(category_id=125).head()
                            group_id   notes                   created  popularity  series_count
            name
            headline figure      gen         2013-11-19 19:55:53+00:00          53             2
            primary              gen         2012-02-27 16:18:19+00:00          42             2
            transfers            gen         2012-02-27 16:18:19+00:00          31             2
            census               src  Census 2012-02-27 16:18:19+00:00          80             4
            investment           gen         2012-02-27 16:18:19+00:00          56             4
        ```
        """
        allowed_orders = [
            enums.OrderBy.series_count,
            enums.OrderBy.popularity,
            enums.OrderBy.created,
            enums.OrderBy.name,
            enums.OrderBy.group_id
        ]

        allowed_tag_group_ids = [
            enums.TagGroupID.frequency,
            enums.TagGroupID.general_or_concept,
            enums.TagGroupID.geography,
            enums.TagGroupID.geography_type,
            enums.TagGroupID.release,
            enums.TagGroupID.seasonal_adjustment,
            enums.TagGroupID.source
        ]

        if order_by not in allowed_orders:
            raise ValueError('Variable order_by ({}) is not one of the values: {}'.format(order_by, ', '.join(map(str, allowed_orders))))

        if tag_group_id is not None and tag_group_id not in allowed_tag_group_ids:
            raise ValueError('Variable tag_group_id is not one of the values: {}'.format(', '.join(map(str, allowed_tag_group_ids))))

        if realtime_start is not None and realtime_start < date(1776, 7, 4):
            raise ValueError('Variable realtime_start ("{}") is before min date 1776-07-04.'.format(realtime_start))

        if realtime_start is not None and realtime_end is not None and realtime_start > realtime_end:
            raise ValueError('The date set by variable realtime_start ("{}") can not be after the date set by variable realtime_end ("{}").'.format(realtime_start, realtime_end))

        df = pd.DataFrame(
            self._client.get(
                '/fred/category/tags',
                'tags',
                limit=1000,
                category_id=category_id,
                realtime_start=realtime_start,
                realtime_end=realtime_end,
                tag_names=tag_names,
                tag_group_id=tag_group_id,
                search_text=search_text,
                order_by=order_by,
                sort_order=sort_order
            )
        )

        if not df.empty:
            df.created = pd.to_datetime(df.created + '00', utc=True, format='%Y-%m-%d %H:%M:%S%z')

            df = df.astype(dtype={
                'name': 'string',
                'notes': 'string',
                'group_id': 'category'
            }).set_index('name')

        return df

    def category_related_tags(
            self,
            category_id: int = 0,
            realtime_start: date = None,
            realtime_end: date = None,
            tag_names: List[str] = None,
            exclude_tag_names: List[str] = None,
            tag_group_id: enums.TagGroupID = None,
            search_text: str = None,
            order_by: enums.OrderBy = enums.OrderBy.series_count,
            sort_order: enums.SortOrder = enums.SortOrder.asc
    ) -> pd.DataFrame:
        """
        ## Parameters

        `category_id`
        The id for a category.

        `realtime_start`
        The start of the real-time period. For more information, see [Real-Time Periods](https://fred.stlouisfed.org/docs/api/fred/realtime_period.html).

        `realtime_end`
        The end of the real-time period. For more information, see [Real-Time Periods](https://fred.stlouisfed.org/docs/api/fred/realtime_period.html).

        `tag_names`
        Tuple of tag names that series match all of.

        `exclude_tag_names`
        Tuple of tag names that series match none of.

        `tag_group_id`
        A tag group id to filter tags by type.

        `search_text`
        The words to find matching tags with.

        `order_by`
        Order results by values of the specified attribute.

        `sort_order`
        Sort results is ascending or descending order for attribute values specified by order_by.

        ## Description
        https://fred.stlouisfed.org/docs/api/fred/category_related_tags.html

        Get the related FRED tags for one or more FRED tags within a category.
        Optionally, filter results by tag group or search.
        FRED tags are attributes assigned to series.
        For this request, related FRED tags are the tags assigned to series that match all tags in the tag_names parameter, no tags in the exclude_tag_names parameter, and the category set by the category_id parameter.
        See the related request fred/category/tags.
        Series are assigned tags and categories. Indirectly through series, it is possible to get the tags for a category.
        No tags exist for a category that does not have series.

        ## API Request (HTTPS GET)
        https://api.stlouisfed.org/fred/category/related_tags?category_id=125&tag_names=services;quarterly&api_key=abcdefghijklmnopqrstuvwxyz123456&file_type=json

        ## API Response
        ```json
        {
            "realtime_start": "2013-08-13",
            "realtime_end": "2013-08-13",
            "order_by": "series_count",
            "sort_order": "desc",
            "count": 7,
            "offset": 0,
            "limit": 1000,
            "tags": [
                {
                    "name": "balance",
                    "group_id": "gen",
                    "notes": "",
                    "created": "2012-02-27 10:18:19-06",
                    "popularity": 65,
                    "series_count": 4
                },
                ...
            ]
        }
        ```

        ## Returns
        `pandas.DataFrame`

        ## Example
        ```python
        >>> fred = FRED(api_key='abcdefghijklmnopqrstuvwxyz123456')
        >>> fred.category_related_tags(category_id=125, tag_names=['services', 'quarterly']).head()
                         group_id                    notes                   created  popularity  series_count
            name
            discontinued      gen                          2012-02-27 16:18:19+00:00          67             4
            nsa              seas  Not Seasonally Adjusted 2012-02-27 16:18:19+00:00         100             6
            sa               seas      Seasonally Adjusted 2012-02-27 16:18:19+00:00          88             6
            goods             gen                          2012-02-27 16:18:19+00:00          68             8
            balance           gen                          2012-02-27 16:18:19+00:00          47            12
        ```
        """

        allowed_orders = [
            enums.OrderBy.series_count,
            enums.OrderBy.popularity,
            enums.OrderBy.created,
            enums.OrderBy.name,
            enums.OrderBy.group_id
        ]

        if order_by not in allowed_orders:
            raise ValueError('Variable order_by ({}) is not one of the values: {}'.format(order_by, ', '.join(map(str, allowed_orders))))

        if realtime_start is not None and realtime_start < date(1776, 7, 4):
            raise ValueError('Variable realtime_start ("{}") is before min date 1776-07-04.'.format(realtime_start))

        if realtime_start is not None and realtime_end is not None and realtime_start > realtime_end:
            raise ValueError('The date set by variable realtime_start ("{}") can not be after the date set by variable realtime_end ("{}").'.format(realtime_start, realtime_end))

        df = pd.DataFrame(
            self._client.get(
                '/fred/category/related_tags',
                'tags',
                limit=1000,
                category_id=category_id,
                realtime_start=realtime_start,
                realtime_end=realtime_end,
                tag_names=tag_names,
                exclude_tag_names=exclude_tag_names,
                tag_group_id=tag_group_id,
                search_text=search_text,
                order_by=order_by,
                sort_order=sort_order
            )
        )

        if not df.empty:
            df.created = pd.to_datetime(df.created + '00', utc=True, format='%Y-%m-%d %H:%M:%S%z')

            df = df.astype(dtype={
                'name': 'string',
                'notes': 'string',
                'group_id': 'category'
            }).set_index('name')

        return df

    """
    Releases

    https://fred.stlouisfed.org/releases
    """

    def releases(
            self,
            realtime_start: date = None,
            realtime_end: date = None,
            order_by: enums.OrderBy = enums.OrderBy.release_id,
            sort_order: enums.SortOrder = enums.SortOrder.asc
    ) -> pd.DataFrame:
        """
        ## Parameters

        `realtime_start`
        The start of the real-time period. For more information, see [Real-Time Periods](https://fred.stlouisfed.org/docs/api/fred/realtime_period.html).

        `realtime_end`
        The end of the real-time period. For more information, see [Real-Time Periods](https://fred.stlouisfed.org/docs/api/fred/realtime_period.html).

        `order_by`
        Order results by values of the specified attribute.

        `sort_order`
        Sort results is ascending or descending order for attribute values specified by order_by.

        ## Description
        https://fred.stlouisfed.org/docs/api/fred/releases.html

        Get all releases of economic data.

        ## API Request (HTTPS GET)
        https://api.stlouisfed.org/fred/releases?api_key=abcdefghijklmnopqrstuvwxyz123456&file_type=json

        ## API Response
        ```json
        {
            "realtime_start": "2013-08-13",
            "realtime_end": "2013-08-13",
            "order_by": "release_id",
            "sort_order": "asc",
            "count": 158,
            "offset": 0,
            "limit": 1000,
            "releases": [
                {
                    "id": 9,
                    "realtime_start": "2013-08-13",
                    "realtime_end": "2013-08-13",
                    "name": "Advance Monthly Sales for Retail and Food Services",
                    "press_release": true,
                    "link": "http://www.census.gov/retail/"
                },
                ...
            ]
        }
        ```

        ## Returns
        `pandas.DataFrame`

        ## Example
        ```python
        >>> fred = FRED(api_key='abcdefghijklmnopqrstuvwxyz123456')
        >>> fred.releases().head()
               realtime_start realtime_end                                               name  press_release                                         link                                              notes
            id
            9      2022-02-05   2022-02-05  Advance Monthly Sales for Retail and Food Serv...           True                http://www.census.gov/retail/  The U.S. Census Bureau conducts the Advance Mo...
            10     2022-02-05   2022-02-05                               Consumer Price Index           True                      http://www.bls.gov/cpi/                                               <NA>
            11     2022-02-05   2022-02-05                              Employment Cost Index           True                  http://www.bls.gov/ncs/ect/                                               <NA>
            13     2022-02-05   2022-02-05  G.17 Industrial Production and Capacity Utiliz...           True  http://www.federalreserve.gov/releases/g17/                                               <NA>
            14     2022-02-05   2022-02-05                               G.19 Consumer Credit           True  http://www.federalreserve.gov/releases/g19/                                               <NA>
        ```
        """

        allowed_orders = [
            enums.OrderBy.release_id,
            enums.OrderBy.name,
            enums.OrderBy.press_release,
            enums.OrderBy.realtime_start,
            enums.OrderBy.realtime_end
        ]

        if order_by not in allowed_orders:
            raise ValueError('Variable order_by ({}) is not one of the values: {}'.format(order_by, ', '.join(map(str, allowed_orders))))

        if realtime_start is not None and realtime_start < date(1776, 7, 4):
            raise ValueError('Variable realtime_start ("{}") is before min date 1776-07-04.'.format(realtime_start))

        if realtime_start is not None and realtime_end is not None and realtime_start > realtime_end:
            raise ValueError('The date set by variable realtime_start ("{}") can not be after the date set by variable realtime_end ("{}").'.format(realtime_start, realtime_end))

        df = pd.DataFrame(
            self._client.get(
                '/fred/releases',
                'releases',
                limit=1000,
                realtime_start=realtime_start,
                realtime_end=realtime_end,
                order_by=order_by,
                sort_order=sort_order
            )
        )

        date_columns = ['realtime_start', 'realtime_end']

        if not df.empty:
            df[date_columns] = df[date_columns].apply(pd.to_datetime, format='%Y-%m-%d')

            df = df.astype(dtype={
                'name': 'string',
                'link': 'string',
                'notes': 'string',
                'press_release': 'bool'
            }).set_index('id')

        return df

    def releases_dates(
            self,
            realtime_start: date = None,
            realtime_end: date = None,
            order_by: enums.OrderBy = enums.OrderBy.release_id,
            sort_order: enums.SortOrder = enums.SortOrder.desc,
            include_release_dates_with_no_data: bool = False
    ) -> pd.DataFrame:
        """
        ## Parameters

        `realtime_start`
        The start of the real-time period. For more information, see [Real-Time Periods](https://fred.stlouisfed.org/docs/api/fred/realtime_period.html).

        `realtime_end`
        The end of the real-time period. For more information, see [Real-Time Periods](https://fred.stlouisfed.org/docs/api/fred/realtime_period.html).

        `order_by`
        Order results by values of the specified attribute.

        `sort_order`
        Sort results is ascending or descending order for attribute values specified by order_by.

        `include_release_dates_with_no_data`
        Determines whether release dates with no data available are returned.
        The defalut value 'false' excludes release dates that do not have data.
        In particular, this excludes future release dates which may be available in the FRED release calendar or the ALFRED release calendar.
        If include_release_dates_with_no_data is set to true, the XML tag release_date has an extra attribute release_last_updated that can be compared to the release date to determine if data has been updated.

        ## Description
        https://fred.stlouisfed.org/docs/api/fred/releases_dates.html

        Get release dates for all releases of economic data.
        Note that release dates are published by data sources and do not necessarily represent when data will be available on the FRED or ALFRED websites.

        ## API Request (HTTPS GET)
        https://api.stlouisfed.org/fred/releases/dates?api_key=abcdefghijklmnopqrstuvwxyz123456&file_type=json

        ## API Response
        ```json
        {
            "realtime_start": "2013-01-01",
            "realtime_end": "9999-12-31",
            "order_by": "release_date",
            "sort_order": "desc",
            "count": 1129,
            "offset": 0,
            "limit": 1000,
            "release_dates": [
                {
                    "release_id": 9,
                    "release_name": "Advance Monthly Sales for Retail and Food Services",
                    "date": "2013-08-13"
                },
                ...
            ]
        }
        ```

        ## Returns
        `pandas.DataFrame`

        ## Example
        ```python
        >>> fred = FRED(api_key='abcdefghijklmnopqrstuvwxyz123456')
        >>> fred.releases_dates(realtime_start=date.today() - timedelta(days=1)).head()
                                                             release_name       date
            release_id
            502                                      Euro Short Term Rate 2022-02-04
            492                             SONIA Interest Rate Benchmark 2022-02-04
            484                                    Key ECB Interest Rates 2022-02-04
            483                              SOFR Averages and Index Data 2022-02-04
            469         State Unemployment Insurance Weekly Claims Report 2022-02-04
        ```
        """
        allowed_orders = [
            enums.OrderBy.release_date,
            enums.OrderBy.release_id,
            enums.OrderBy.release_name,
        ]

        if order_by not in allowed_orders:
            raise ValueError('Variable order_by ({}) is not one of the values: {}'.format(order_by, ', '.join(map(str, allowed_orders))))

        if realtime_start is not None and realtime_start < date(1776, 7, 4):
            raise ValueError('Variable realtime_start ("{}") is before min date 1776-07-04.'.format(realtime_start))

        if realtime_start is not None and realtime_end is not None and realtime_start > realtime_end:
            raise ValueError('The date set by variable realtime_start ("{}") can not be after the date set by variable realtime_end ("{}").'.format(realtime_start, realtime_end))

        df = pd.DataFrame(
            self._client.get(
                '/fred/releases/dates',
                'release_dates',
                limit=1000,
                realtime_start=realtime_start,
                realtime_end=realtime_end,
                order_by=order_by,
                sort_order=sort_order,
                include_release_dates_with_no_data=include_release_dates_with_no_data
            )
        )

        if not df.empty:
            df.date = pd.to_datetime(df.date, format='%Y-%m-%d')
            df = df.astype(dtype={
                'release_name': 'string'
            }).set_index('release_id')

        return df

    def release(self, release_id: int, realtime_start: date = None, realtime_end: date = None) -> models.Release:
        """
        ## Parameters
        `release_id`
        The id for a release.

        `realtime_start`
        The start of the real-time period. For more information, see [Real-Time Periods](https://fred.stlouisfed.org/docs/api/fred/realtime_period.html).

        `realtime_end`
        The end of the real-time period. For more information, see [Real-Time Periods](https://fred.stlouisfed.org/docs/api/fred/realtime_period.html).

        ## Description
        https://fred.stlouisfed.org/docs/api/fred/release.html

        Get a release of economic data.

        ## API Request (HTTPS GET)
        https://api.stlouisfed.org/fred/release?release_id=53&api_key=abcdefghijklmnopqrstuvwxyz123456&file_type=json

        ## API Response
        ```json
        {
            "realtime_start": "2013-08-14",
            "realtime_end": "2013-08-14",
            "releases": [
                {
                    "id": 53,
                    "realtime_start": "2013-08-14",
                    "realtime_end": "2013-08-14",
                    "name": "Gross Domestic Product",
                    "press_release": true,
                    "link": "http://www.bea.gov/national/index.htm"
                }
            ]
        };
        ```

        ## Returns
        `pystlouisfed.models.Release`

        ## Example
        ```python
        >>> fred = FRED(api_key='abcdefghijklmnopqrstuvwxyz123456')
        >>> fred.release(release_id=53)
            Release(id=53, realtime_start=datetime.date(2022, 1, 14), realtime_end=datetime.date(2022, 1, 14), name='Gross Domestic Product', press_release=True, link='https://www.bea.gov/data/gdp/gross-domestic-product')
        ```
        """
        if int(release_id) <= 0:
            raise ValueError('Variable release_id is not 0 or a positive integer.')

        if realtime_start is not None and realtime_start < date(1776, 7, 4):
            raise ValueError('Variable realtime_start ("{}") is before min date 1776-07-04.'.format(realtime_start))

        if realtime_start is not None and realtime_end is not None and realtime_start > realtime_end:
            raise ValueError('The date set by variable realtime_start ("{}") can not be after the date set by variable realtime_end ("{}").'.format(realtime_start, realtime_end))

        data = self._client.get(
            '/fred/release',
            'releases',
            release_id=release_id,
            realtime_start=realtime_start,
            realtime_end=realtime_end,
        )

        return models.Release(**data[0])

    def release_dates(
            self,
            release_id: int,
            realtime_start: date = date(1776, 7, 4),
            realtime_end: date = date(9999, 12, 31),
            sort_order: enums.SortOrder = enums.SortOrder.asc,
            include_release_dates_with_no_data: bool = False
    ) -> pd.DataFrame:
        """
        ## Parameters
        `release_id`
        The id for a release.

        `realtime_start`
        The start of the real-time period. For more information, see [Real-Time Periods](https://fred.stlouisfed.org/docs/api/fred/realtime_period.html).

        `realtime_end`
        The end of the real-time period. For more information, see [Real-Time Periods](https://fred.stlouisfed.org/docs/api/fred/realtime_period.html).

        `order_by`
        Order results by values of the specified attribute.

        `sort_order`
        Sort results is ascending or descending order for attribute values specified by order_by.

        ## Description
        https://fred.stlouisfed.org/docs/api/fred/release_dates.html

        Get release dates for a release of economic data.

        ## API Request (HTTPS GET)
        https://api.stlouisfed.org/fred/release/dates?release_id=82&api_key=abcdefghijklmnopqrstuvwxyz123456&file_type=json

        ## API Response
        ```json
        {
            "realtime_start": "1776-07-04",
            "realtime_end": "9999-12-31",
            "order_by": "release_date",
            "sort_order": "asc",
            "count": 17,
            "offset": 0,
            "limit": 10000,
            "release_dates": [
                {
                    "release_id": 82,
                    "date": "1997-02-10"
                },
                ...
            ]
        }
        ```

        ## Returns
        `pandas.DataFrame`

        ## Example
        ```python
        >>> fred = FRED(api_key='abcdefghijklmnopqrstuvwxyz123456')
        >>> fred.release_dates(release_id=82).head()
               release_id       date
            0          82 1997-02-10
            1          82 1998-02-10
            2          82 1999-02-04
            3          82 2000-02-10
            4          82 2001-01-16
        ```
        """

        if realtime_start is not None and realtime_start < date(1776, 7, 4):
            raise ValueError('Variable realtime_start ("{}") is before min date 1776-07-04.'.format(realtime_start))

        if realtime_start > realtime_end:
            raise ValueError('The date set by variable realtime_start ("{}") can not be after the date set by variable realtime_end ("{}").'.format(realtime_start, realtime_end))

        df = pd.DataFrame(
            self._client.get(
                '/fred/release/dates',
                'release_dates',
                limit=10000,
                release_id=release_id,
                realtime_start=realtime_start,
                realtime_end=realtime_end,
                sort_order=sort_order,
                include_release_dates_with_no_data=include_release_dates_with_no_data
            )
        )

        if not df.empty:
            df.date = pd.to_datetime(df.date, format='%Y-%m-%d')

        return df

    def release_series(
            self,
            release_id: int,
            realtime_start: date = None,
            realtime_end: date = None,
            order_by: enums.OrderBy = enums.OrderBy.series_id,
            sort_order: enums.SortOrder = enums.SortOrder.asc,
            filter_variable: enums.FilterVariable = None,
            filter_value: enums.FilterValue = None,
            tag_names: List[str] = None,
            exclude_tag_names: List[str] = None
    ) -> pd.DataFrame:
        """
        ## Parameters

        `release_id`
        The id for a release.

        `realtime_start`
        The start of the real-time period. For more information, see [Real-Time Periods](https://fred.stlouisfed.org/docs/api/fred/realtime_period.html).

        `realtime_end`
        The end of the real-time period. For more information, see [Real-Time Periods](https://fred.stlouisfed.org/docs/api/fred/realtime_period.html).

        `order_by`
        Order results by values of the specified attribute.

        `sort_order`
        Sort results is ascending or descending order for attribute values specified by order_by.

        `filter_variable`
        The attribute to filter results by.

        `filter_value`
        The value of the filter_variable attribute to filter results by.

        `tag_names`
        Tuple of tag names that series match all of.

        `exclude_tag_names`
        Tuple of tag names that series match none of.

        ## Description
        https://fred.stlouisfed.org/docs/api/fred/release_series.html

        Get the series on a release of economic data.

        ## API Request (HTTPS GET)
        https://api.stlouisfed.org/fred/release/series?release_id=51&api_key=abcdefghijklmnopqrstuvwxyz123456&file_type=json

        ## API Response
        ```json
        {
          "realtime_start": "2017-08-01",
          "realtime_end": "2017-08-01",
          "order_by": "series_id",
          "sort_order": "asc",
          "count": 57,
          "offset": 0,
          "limit": 1000,
          "seriess": [
                {
                  "id": "BOMTVLM133S",
                  "realtime_start": "2017-08-01",
                  "realtime_end": "2017-08-01",
                  "title": "U.S. Imports of Services - Travel",
                  "observation_start": "1992-01-01",
                  "observation_end": "2017-05-01",
                  "frequency": "Monthly",
                  "frequency_short": "M",
                  "units": "Million of Dollars",
                  "units_short": "Mil. of $",
                  "seasonal_adjustment": "Seasonally Adjusted",
                  "seasonal_adjustment_short": "SA",
                  "last_updated": "2017-07-06 09:34:00-05",
                  "popularity": 0,
                  "group_popularity": 0
                },
                ...
            ]
        )
        ```

        ## Returns
        `pandas.DataFrame`

        ## Example
        ```python
        >>> fred = FRED(api_key='abcdefghijklmnopqrstuvwxyz123456')
        >>> fred.release_series(release_id=51).head()
                        realtime_start realtime_end                                              title observation_start observation_end frequency frequency_short                units units_short  seasonal_adjustment seasonal_adjustment_short              last_updated  popularity  group_popularity                                              notes
            id
            BOMTVLM133S     2022-02-05   2022-02-05                  U.S. Imports of Services - Travel        1992-01-01      2017-09-01   Monthly               M   Million of Dollars   Mil. of $  Seasonally Adjusted                        SA 2017-11-03 13:12:15+00:00           1                 1  Further information related to the internation...
            BOMVGMM133S     2022-02-05   2022-02-05  U.S. Imports of Services: U.S. Government Misc...        1992-01-01      2013-12-01   Monthly               M  Millions of Dollars   Mil. of $  Seasonally Adjusted                        SA 2014-10-20 14:27:37+00:00           1                 1  BEA has introduced new table presentations, in...
            BOMVJMM133S     2022-02-05   2022-02-05  U.S. Imports of Services - Direct Defense Expe...        1992-01-01      2013-12-01   Monthly               M  Millions of Dollars   Mil. of $  Seasonally Adjusted                        SA 2014-10-20 14:26:44+00:00           1                 1  BEA has introduced new table presentations, in...
            BOMVMPM133S     2022-02-05   2022-02-05         U.S. Imports of Services - Passenger Fares        1992-01-01      2017-09-01   Monthly               M   Million of Dollars   Mil. of $  Seasonally Adjusted                        SA 2017-11-03 13:12:15+00:00           1                 1  Further information related to the internation...
            BOMVOMM133S     2022-02-05   2022-02-05  U.S. Imports of Services - Other Private Servi...        1992-01-01      2013-12-01   Monthly               M   Million of Dollars   Mil. of $  Seasonally Adjusted                        SA 2014-10-20 14:25:54+00:00           1                 1  BEA has introduced new table presentations, in...
        ```
        """

        allowed_orders = [
            enums.OrderBy.series_id,
            enums.OrderBy.title,
            enums.OrderBy.units,
            enums.OrderBy.frequency,
            enums.OrderBy.seasonal_adjustment,
            enums.OrderBy.realtime_start,
            enums.OrderBy.realtime_end,
            enums.OrderBy.last_updated,
            enums.OrderBy.observation_start,
            enums.OrderBy.observation_end,
            enums.OrderBy.popularity,
            enums.OrderBy.group_popularity,
        ]

        if order_by not in allowed_orders:
            raise ValueError('Variable order_by ({}) is not one of the values: {}'.format(order_by, ', '.join(map(str, allowed_orders))))

        if filter_variable is not None and filter_variable not in enums.FilterVariable:
            raise ValueError('Variable allowed_filter_variables ({}) is not one of the values: {}'.format(filter_variable, ', '.join(map(str, enums.FilterVariable))))

        if realtime_start is not None and realtime_start < date(1776, 7, 4):
            raise ValueError('Variable realtime_start ("{}") is before min date 1776-07-04.'.format(realtime_start))

        if realtime_start is not None and realtime_end is not None and realtime_start > realtime_end:
            raise ValueError('The date set by variable realtime_start ("{}") can not be after the date set by variable realtime_end ("{}").'.format(realtime_start, realtime_end))

        df = pd.DataFrame(
            self._client.get(
                '/fred/release/series',
                'seriess',
                limit=1000,
                release_id=release_id,
                realtime_start=realtime_start,
                realtime_end=realtime_end,
                order_by=order_by,
                sort_order=sort_order,
                filter_variable=filter_variable,
                filter_value=filter_value,
                tag_names=tag_names,
                exclude_tag_names=exclude_tag_names
            )
        )

        date_columns = [
            'realtime_start', 'realtime_end',
            'observation_start', 'observation_end',
        ]

        if not df.empty:
            df[date_columns] = df[date_columns].apply(pd.to_datetime, format='%Y-%m-%d')
            df.last_updated = pd.to_datetime(df.last_updated + '00', utc=True, format='%Y-%m-%d %H:%M:%S%z')

            df = df.astype(dtype={
                'id': 'string',
                'title': 'string',
                'notes': 'string',
                'frequency': 'category',
                'frequency_short': 'category',
                'units': 'category',
                'units_short': 'category',
                'seasonal_adjustment': 'category',
                'seasonal_adjustment_short': 'category'
            }).set_index('id')

        return df

    def release_sources(self, release_id: int, realtime_start: date = None, realtime_end: date = None) -> pd.DataFrame:
        """
        ## Parameters

        `release_id`
        The id for a release.

        `realtime_start`
        The start of the real-time period. For more information, see [Real-Time Periods](https://fred.stlouisfed.org/docs/api/fred/realtime_period.html).

        `realtime_end`
        The end of the real-time period. For more information, see [Real-Time Periods](https://fred.stlouisfed.org/docs/api/fred/realtime_period.html).

        ## Description
        https://fred.stlouisfed.org/docs/api/fred/release_sources.html

        Get the sources for a release of economic data.

        ## API Request (HTTPS GET)
        https://api.stlouisfed.org/fred/release/sources?release_id=51&api_key=abcdefghijklmnopqrstuvwxyz123456&file_type=json

        ## API Response
        ```json
        {
            "realtime_start": "2013-08-14",
            "realtime_end": "2013-08-14",
            "sources": [
                {
                    "id": 18,
                    "realtime_start": "2013-08-14",
                    "realtime_end": "2013-08-14",
                    "name": "U.S. Department of Commerce: Bureau of Economic Analysis",
                    "link": "http://www.bea.gov/"
                },
                ...
            ]
        }
        ```

        ## Returns
        `pandas.DataFrame`

        ## Example
        ```python
        >>> fred = FRED(api_key='abcdefghijklmnopqrstuvwxyz123456')
        >>> fred.release_sources(release_id=51).head()
               realtime_start realtime_end                              name                    link
            id
            19     2022-02-05   2022-02-05                U.S. Census Bureau  http://www.census.gov/
            18     2022-02-05   2022-02-05  U.S. Bureau of Economic Analysis     http://www.bea.gov/
        """

        if realtime_start is not None and realtime_start < date(1776, 7, 4):
            raise ValueError('Variable realtime_start ("{}") is before min date 1776-07-04.'.format(realtime_start))

        if realtime_start is not None and realtime_end is not None and realtime_start > realtime_end:
            raise ValueError('The date set by variable realtime_start ("{}") can not be after the date set by variable realtime_end ("{}").'.format(realtime_start, realtime_end))

        df = pd.DataFrame(
            self._client.get(
                '/fred/release/sources',
                'sources',
                release_id=release_id,
                realtime_start=realtime_start,
                realtime_end=realtime_end
            )
        )

        date_columns = ['realtime_start', 'realtime_end']

        if not df.empty:
            df[date_columns] = df[date_columns].apply(pd.to_datetime, format='%Y-%m-%d')
            df = df.astype(dtype={
                'name': 'string',
                'link': 'string'
            }).set_index('id')

        return df

    def release_tags(
            self,
            release_id: int,
            realtime_start: date = None,
            realtime_end: date = None,
            tag_names: List[str] = None,
            tag_group_id: enums.TagGroupID = None,
            search_text: str = None,
            order_by: enums.OrderBy = enums.OrderBy.series_count,
            sort_order: enums.SortOrder = enums.SortOrder.asc
    ) -> pd.DataFrame:
        """
        ## Parameters

        `release_id`
        The id for a release.

        `realtime_start`
        The start of the real-time period. For more information, see [Real-Time Periods](https://fred.stlouisfed.org/docs/api/fred/realtime_period.html).

        `realtime_end`
        The end of the real-time period. For more information, see [Real-Time Periods](https://fred.stlouisfed.org/docs/api/fred/realtime_period.html).

        `tag_names`
        Tuple of tag names that series match all of.

        `tag_group_id`
        A tag group id to filter tags by type.

        `search_text`
        The words to find matching tags with.

        `order_by`
        Order results by values of the specified attribute.

        `sort_order`
        Sort results is ascending or descending order for attribute values specified by order_by.

        ## Description
        https://fred.stlouisfed.org/docs/api/fred/release_tags.html

        Get the FRED tags for a release.
        Optionally, filter results by tag name, tag group, or search.
        Series are assigned tags and releases.
        Indirectly through series, it is possible to get the tags for a release.
        See the related request fred/release/related_tags.

        ## API Request (HTTPS GET)
        https://api.stlouisfed.org/fred/release/tags?release_id=86&api_key=abcdefghijklmnopqrstuvwxyz123456&file_type=json

        ## API Response
        ```json
        {
            "realtime_start": "2013-08-14",
            "realtime_end": "2013-08-14",
            "order_by": "series_count",
            "sort_order": "desc",
            "count": 13,
            "offset": 0,
            "limit": 1000,
            "tags": [
                {
                    "name": "commercial paper",
                    "group_id": "gen",
                    "notes": "",
                    "created": "2012-03-19 10:40:59-05",
                    "popularity": 55,
                    "series_count": 18
                },
                ...
            ]
        }
        ```

        ## Returns
        `pandas.DataFrame`

        ## Example
        ```python
        >>> fred = FRED(api_key='abcdefghijklmnopqrstuvwxyz123456')
        >>> fred.release_tags(release_id=86).head()
                       group_id notes                   created  popularity  series_count
            name
            1-month         gen       2012-02-27 16:18:19+00:00          39             2
            2-month         gen       2012-05-25 16:29:21+00:00          17             2
            owned           gen       2012-06-25 20:04:36+00:00          33             2
            tier-2          gen       2014-02-12 17:18:16+00:00         -13             2
            10-20 days      gen       2014-02-12 17:08:07+00:00         -16             4
        """

        allowed_orders = [
            enums.OrderBy.series_count,
            enums.OrderBy.popularity,
            enums.OrderBy.created,
            enums.OrderBy.name,
            enums.OrderBy.group_id,
        ]

        if order_by not in allowed_orders:
            raise ValueError('Variable order_by ({}) is not one of the values: {}'.format(order_by, ', '.join(map(str, allowed_orders))))

        if realtime_start is not None and realtime_start < date(1776, 7, 4):
            raise ValueError('Variable realtime_start ("{}") is before min date 1776-07-04.'.format(realtime_start))

        if realtime_start is not None and realtime_end is not None and realtime_start > realtime_end:
            raise ValueError('The date set by variable realtime_start ("{}") can not be after the date set by variable realtime_end ("{}").'.format(realtime_start, realtime_end))

        df = pd.DataFrame(
            self._client.get(
                '/fred/release/tags',
                'tags',
                limit=1000,
                release_id=release_id,
                realtime_start=realtime_start,
                realtime_end=realtime_end,
                tag_names=tag_names,
                tag_group_id=tag_group_id,
                search_text=search_text,
                order_by=order_by,
                sort_order=sort_order
            )
        )

        if not df.empty:
            df.created = pd.to_datetime(df.created + '00', utc=True, format='%Y-%m-%d %H:%M:%S%z')

            df = df.astype(dtype={
                'name': 'string',
                'notes': 'string',
                'group_id': 'category'
            }).set_index('name')

        return df

    def release_related_tags(
            self,
            release_id: int,
            realtime_start: date = None,
            realtime_end: date = None,
            tag_names: List[str] = None,
            exclude_tag_names: List[str] = None,
            tag_group_id: enums.TagGroupID = None,
            search_text: str = None,
            order_by: enums.OrderBy = enums.OrderBy.series_count,
            sort_order: enums.SortOrder = enums.SortOrder.asc
    ) -> pd.DataFrame:
        """
        ## Parameters

        `release_id`
        The id for a release.

        `realtime_start`
        The start of the real-time period. For more information, see [Real-Time Periods](https://fred.stlouisfed.org/docs/api/fred/realtime_period.html).

        `realtime_end`
        The end of the real-time period. For more information, see [Real-Time Periods](https://fred.stlouisfed.org/docs/api/fred/realtime_period.html).

        `tag_names`
        Tuple of tag names that series match all of.

        `exclude_tag_names`
        Tuple of tag names that series match none of.

        `tag_group_id`
        A tag group id to filter tags by type.

        `search_text`
        The words to find matching tags with.

        `order_by`
        Order results by values of the specified attribute.

        `sort_order`
        Sort results is ascending or descending order for attribute values specified by order_by.

        ## Description
        https://fred.stlouisfed.org/docs/api/fred/release_related_tags.html

        Get the related FRED tags for one or more FRED tags within a release. Optionally, filter results by tag group or search.
        FRED tags are attributes assigned to series.
        For this request, related FRED tags are the tags assigned to series that match all tags in the tag_names parameter, no tags in the exclude_tag_names parameter, and the release set by the release_id parameter.
        See the related request fred/release/tags.
        Series are assigned tags and releases. Indirectly through series, it is possible to get the tags for a release.

        ## API Request (HTTPS GET)
        https://api.stlouisfed.org/fred/release/related_tags?release_id=86&tag_names=sa;foreign&api_key=abcdefghijklmnopqrstuvwxyz123456&file_type=json

        ## API Response
        ```json
        {
            "realtime_start": "2013-08-14",
            "realtime_end": "2013-08-14",
            "order_by": "series_count",
            "sort_order": "desc",
            "count": 7,
            "offset": 0,
            "limit": 1000,
            "tags": [
                {
                    "name": "commercial paper",
                    "group_id": "gen",
                    "notes": "",
                    "created": "2012-03-19 10:40:59-05",
                    "popularity": 55,
                    "series_count": 2
                },
                ...
            ]
        }
        ```

        ## Returns
        `pandas.DataFrame`

        ## Example
        ```python
        >>> fred = FRED(api_key='abcdefghijklmnopqrstuvwxyz123456')
        >>> fred.release_related_tags(release_id=86, tag_names=['sa', 'foreign']).head()
                         group_id notes                   created  popularity  series_count
            name
            financial         gen       2012-02-27 16:18:19+00:00          55             2
            monthly          freq       2012-02-27 16:18:19+00:00          93             2
            nonfinancial      gen       2012-02-27 16:18:19+00:00          55             2
            weekly           freq       2012-02-27 16:18:19+00:00          68             2
            commercial        gen       2012-02-27 16:18:19+00:00          61             4
        ```
        """

        allowed_orders = [
            enums.OrderBy.series_count,
            enums.OrderBy.popularity,
            enums.OrderBy.created,
            enums.OrderBy.name,
            enums.OrderBy.group_id,
        ]

        if order_by not in allowed_orders:
            raise ValueError('Variable order_by ({}) is not one of the values: {}'.format(order_by, ', '.join(map(str, allowed_orders))))

        if realtime_start is not None and realtime_start < date(1776, 7, 4):
            raise ValueError('Variable realtime_start ("{}") is before min date 1776-07-04.'.format(realtime_start))

        if realtime_start is not None and realtime_end is not None and realtime_start > realtime_end:
            raise ValueError('The date set by variable realtime_start ("{}") can not be after the date set by variable realtime_end ("{}").'.format(realtime_start, realtime_end))

        df = pd.DataFrame(
            self._client.get(
                '/fred/release/related_tags',
                'tags',
                limit=1000,
                release_id=release_id,
                realtime_start=realtime_start,
                realtime_end=realtime_end,
                tag_names=tag_names,
                exclude_tag_names=exclude_tag_names,
                tag_group_id=tag_group_id,
                search_text=search_text,
                order_by=order_by,
                sort_order=sort_order
            )
        )

        if not df.empty:
            df.created = pd.to_datetime(df.created + '00', utc=True, format='%Y-%m-%d %H:%M:%S%z')

            df = df.astype(dtype={
                'name': 'string',
                'notes': 'string',
                'group_id': 'category'
            }).set_index('name')

        return df

    def release_tables(
            self,
            release_id: int,
            element_id: int = None,
            include_observation_values: bool = False,
            observation_date: date = date(9999, 12, 31)
    ) -> pd.DataFrame:
        """
        ## Parameters

        `release_id`
        The id for a release.

        `element_id`
        The release table element id you would like to retrieve.
        When the parameter is not passed, the root(top most) element for the release is given.

        `include_observation_values`
        A flag to indicate that observations need to be returned. Observation value and date will only be returned for a series type element.

        `observation_date`
        The observation date to be included with the returned release table.

        ## Description
        https://fred.stlouisfed.org/docs/api/fred/release_tables.html

        Get release table trees for a given release.
        You can go directly to the tree structure by passing the appropriate element_id.
        You may also use a drill-down approach to start at the root (top most) element by leaving the element_id off.
        Note that release dates are published by data sources and do not necessarily represent when data will be available on the FRED or ALFRED websites.

        ## API Request (HTTPS GET)
        https://api.stlouisfed.org/fred/release/tables?release_id=53&api_key=abcdefghijklmnopqrstuvwxyz123456&element_id=12886&file_type=json

        ## API Response
        ```json
        {
            {
            "name": "Personal consumption expenditures",
            "element_id": 12886,
            "release_id": "53",
            "elements": {
            "12887": {
                "element_id": 12887,
                "release_id": 53,
                "series_id": "DGDSRL1A225NBEA",
                "parent_id": 12886,
                "line": "3",
                "type": "series",
                "name": "Goods",
                "level": "1",
                "children": [
                    {
                        "element_id": 12888,
                        "release_id": 53,
                        "series_id": "DDURRL1A225NBEA",
                        "parent_id": 12887,
                        "line": "4",
                        "type": "series",
                        "name": "Durable goods",
                        "level": "2",
                        "children": [

                        ]
                    },
                    ...
                ]
            }
        }
        ```
        """

        raise NotImplementedError('Method "FRED.release_tables" is not implemented')

    """
    Series

    """

    def series(self, series_id: str, realtime_start: date = None, realtime_end: date = None) -> models.Series:
        """
        ## Parameters

        `series_id`
        The id for a series.

        `realtime_start`
        The start of the real-time period. For more information, see [Real-Time Periods](https://fred.stlouisfed.org/docs/api/fred/realtime_period.html).

        `realtime_end`
        The end of the real-time period. For more information, see [Real-Time Periods](https://fred.stlouisfed.org/docs/api/fred/realtime_period.html).

        ## Description
        https://fred.stlouisfed.org/docs/api/fred/series.html

        Get an economic data series.

        ## API Request (HTTPS GET)
        https://api.stlouisfed.org/fred/series?series_id=GNPCA&api_key=abcdefghijklmnopqrstuvwxyz123456&file_type=json

        ## API Response
        ```json
        {
            "realtime_start": "2013-08-14",
            "realtime_end": "2013-08-14",
            "seriess": [
                {
                    "id": "GNPCA",
                    "realtime_start": "2013-08-14",
                    "realtime_end": "2013-08-14",
                    "title": "Real Gross National Product",
                    "observation_start": "1929-01-01",
                    "observation_end": "2012-01-01",
                    "frequency": "Annual",
                    "frequency_short": "A",
                    "units": "Billions of Chained 2009 Dollars",
                    "units_short": "Bil. of Chn. 2009 $",
                    "seasonal_adjustment": "Not Seasonally Adjusted",
                    "seasonal_adjustment_short": "NSA",
                    "last_updated": "2013-07-31 09:26:16-05",
                    "popularity": 39,
                    "notes": "BEA Account Code: A001RX1"
                }
            ]
        }
        ```

        ## Returns
        `pystlouisfed.models.Series`

        ## Example
        ```python
        >>> fred = FRED(api_key='abcdefghijklmnopqrstuvwxyz123456')
        >>> fred.series(series_id='GNPCA')
            Series(id='GNPCA', realtime_start=datetime.date(2022, 1, 14), realtime_end=datetime.date(2022, 1, 14), title='Real Gross National Product', observation_start=datetime.date(1929, 1, 1), observation_end=datetime.date(2020, 1, 1), frequency='Annual', frequency_short='A', units='Billions of Chained 2012 Dollars', units_short='Bil. of Chn. 2012 $', seasonal_adjustment='Not Seasonally Adjusted', seasonal_adjustment_short='NSA', last_updated=datetime.datetime(2021, 7, 29, 7, 45, 58, tzinfo=datetime.timezone(datetime.timedelta(days=-1, seconds=68400))), popularity=12, notes='BEA Account Code: A001RX\\n\\n')
        ```
        """

        if realtime_start is not None and realtime_start < date(1776, 7, 4):
            raise ValueError('Variable realtime_start ("{}") is before min date 1776-07-04.'.format(realtime_start))

        if realtime_start is not None and realtime_end is not None and realtime_start > realtime_end:
            raise ValueError('The date set by variable realtime_start ("{}") can not be after the date set by variable realtime_end ("{}").'.format(realtime_start, realtime_end))

        data = self._client.get(
            '/fred/series',
            'seriess',
            series_id=series_id,
            realtime_start=realtime_start,
            realtime_end=realtime_end,
        )

        return models.Series(**data[0])

    def series_categories(self, series_id: str, realtime_start: date = None, realtime_end: date = None) -> pd.DataFrame:
        """
        ## Parameters

        `series_id`
        The id for a series.

        `realtime_start`
        The start of the real-time period. For more information, see [Real-Time Periods](https://fred.stlouisfed.org/docs/api/fred/realtime_period.html).

        `realtime_end`
        The end of the real-time period. For more information, see [Real-Time Periods](https://fred.stlouisfed.org/docs/api/fred/realtime_period.html).

        ## Description
        https://fred.stlouisfed.org/docs/api/fred/series_categories.html

        Get the categories for an economic data series.

        ## API Request (HTTPS GET)
        https://api.stlouisfed.org/fred/series/categories?series_id=EXJPUS&api_key=abcdefghijklmnopqrstuvwxyz123456&file_type=json

        ## API Response
        ```json
        {
            "categories": [
                {
                    "id": 95,
                    "name": "Monthly Rates",
                    "parent_id": 15
                }
                ...
            ]
        }
        ```

        ## Returns
        `pandas.DataFrame`

        ## Example
        ```python
        >>> fred = FRED(api_key='abcdefghijklmnopqrstuvwxyz123456')
        >>> fred.series_categories(series_id='EXJPUS')
                          name  parent_id
            id
            95   Monthly Rates         15
            275          Japan        158
        ```
        """

        if realtime_start is not None and realtime_start < date(1776, 7, 4):
            raise ValueError('Variable realtime_start ("{}") is before min date 1776-07-04.'.format(realtime_start))

        if realtime_start is not None and realtime_end is not None and realtime_start > realtime_end:
            raise ValueError('The date set by variable realtime_start ("{}") can not be after the date set by variable realtime_end ("{}").'.format(realtime_start, realtime_end))

        df = pd.DataFrame(
            self._client.get(
                '/fred/series/categories',
                'categories',
                series_id=series_id,
                realtime_start=realtime_start,
                realtime_end=realtime_end,
            )
        ).astype(dtype={
            'name': 'string'
        }).set_index('id')

        return df

    def series_observations(
            self,
            series_id: str,
            realtime_start: date = None,
            realtime_end: date = None,
            sort_order: enums.SortOrder = enums.SortOrder.asc,
            observation_start: date = date(1776, 7, 4),
            observation_end: date = date(9999, 12, 31),
            units: enums.Unit = enums.Unit.lin,
            frequency: enums.Frequency = None,
            aggregation_method: enums.AggregationMethod = enums.AggregationMethod.average,
            output_type: enums.OutputType = enums.OutputType.realtime_period,
            vintage_dates: List[str] = None
    ) -> pd.DataFrame:
        """
        ## Parameters

        `series_id`
        The id for a series.

        `realtime_start`
        The start of the real-time period. For more information, see [Real-Time Periods](https://fred.stlouisfed.org/docs/api/fred/realtime_period.html).

        `realtime_end`
        The end of the real-time period. For more information, see [Real-Time Periods](https://fred.stlouisfed.org/docs/api/fred/realtime_period.html).

        `sort_order`
        Sort results is ascending or descending observation_date order.

        `observation_start`
        The start of the observation period.

        `observation_end`
        The end of the observation period.

        `units`
        A key that indicates a data value transformation.

        `frequency`
        An optional parameter that indicates a lower frequency to aggregate values to.

        `aggregation_method`
        A key that indicates the aggregation method used for frequency aggregation.
        This parameter has no affect if the frequency parameter is not set.

        `output_type`
        An integer that indicates an output type.

        `vintage_dates`
        A comma separated string of YYYY-MM-DD formatted dates in history (e.g. 2000-01-01,2005-02-24).
        Vintage dates are used to download data as it existed on these specified dates in history.
        Vintage dates can be specified instead of a real-time period using realtime_start and realtime_end.
        Sometimes it may be useful to enter a vintage date that is not a date when the data values were revised. For instance you may want to know the latest available revisions on 2001-09-11 (World Trade Center and Pentagon attacks) or as of a Federal Open Market Committee (FOMC) meeting date.
        Entering a vintage date is also useful to compare series on different releases with different release dates.

        ## Description
        https://fred.stlouisfed.org/docs/api/fred/series_observations.html

        Get the observations or data values for an economic data series.

        ## API Request (HTTPS GET)
        https://api.stlouisfed.org/fred/series/observations?series_id=GNPCA&api_key=abcdefghijklmnopqrstuvwxyz123456&file_type=json

        ## API Response
        ```json
        {
            "realtime_start": "2013-08-14",
            "realtime_end": "2013-08-14",
            "observation_start": "1776-07-04",
            "observation_end": "9999-12-31",
            "units": "lin",
            "output_type": 1,
            "file_type": "json",
            "order_by": "observation_date",
            "sort_order": "asc",
            "count": 84,
            "offset": 0,
            "limit": 100000,
            "observations": [
                {
                    "realtime_start": "2013-08-14",
                    "realtime_end": "2013-08-14",
                    "date": "1929-01-01",
                    "value": "1065.9"
                },
                ...
            ]
        }
        ```

        ## Returns
        `pystlouisfed.models.Series`

        ## Example
        ```python
        >>> fred = FRED(api_key='abcdefghijklmnopqrstuvwxyz123456')
        >>> fred.series_observations(series_id='GNPCA').head()
                       realtime_start realtime_end     value
            date
            1929-01-01     2022-02-05   2022-02-05  1120.718
            1930-01-01     2022-02-05   2022-02-05  1025.678
            1931-01-01     2022-02-05   2022-02-05   958.927
            1932-01-01     2022-02-05   2022-02-05   834.769
            1933-01-01     2022-02-05   2022-02-05   823.628
        ```

        ```python
        >>> from matplotlib import pyplot as plt

        >>> fred = FRED(api_key='abcdefghijklmnopqrstuvwxyz123456')
        >>> df = fred.series_observations(series_id='T10Y2Y')
        >>> df.plot(y='value', grid=True)

        >>> plt.show()
        ```
        .. image:: T10Y2Y.png
        """

        if units not in enums.Unit:
            raise ValueError('Variable units ({}) is not one of the values: {}'.format(units, ', '.join(map(str, enums.Unit))))

        if frequency is not None and frequency not in enums.Frequency:
            raise ValueError('Variable frequency ({}) is not one of the values: {}'.format(frequency, ', '.join(map(str, enums.Frequency))))

        if aggregation_method not in enums.AggregationMethod:
            raise ValueError('Variable aggregation_method ({}) is not one of the values: {}'.format(aggregation_method, ', '.join(map(str, enums.AggregationMethod))))

        if output_type not in enums.OutputType:
            raise ValueError('Variable output_type ({}) is not one of the values: {}'.format(output_type, ', '.join(map(str, enums.OutputType))))

        if realtime_start is not None and realtime_start < date(1776, 7, 4):
            raise ValueError('Variable realtime_start ("{}") is before min date 1776-07-04.'.format(realtime_start))

        if realtime_start is not None and realtime_end is not None and realtime_start > realtime_end:
            raise ValueError('The date set by variable realtime_start ("{}") can not be after the date set by variable realtime_end ("{}").'.format(realtime_start, realtime_end))

        df = pd.DataFrame(
            self._client.get(
                '/fred/series/observations',
                'observations',
                limit=100000,
                series_id=series_id,
                realtime_start=realtime_start,
                realtime_end=realtime_end,
                sort_order=sort_order,
                observation_start=observation_start,
                observation_end=observation_end,
                units=units,
                frequency=frequency,
                aggregation_method=aggregation_method,
                output_type=output_type,
                vintage_dates=vintage_dates
            )
        )

        date_columns = ['realtime_start', 'realtime_end', 'date']

        if not df.empty:
            df[date_columns] = df[date_columns].apply(pd.to_datetime, format='%Y-%m-%d')
            df.value = df.value.replace(self.EMPTY_VALUE, np.nan)

            df = df.astype(dtype={
                'value': 'float'
            }).set_index('date')

        return df

    def series_release(self, series_id: str, realtime_start: date = None, realtime_end: date = None) -> pd.DataFrame:
        """
        ## Parameters

        `series_id`
        The id for a series.

        `realtime_start`
        The start of the real-time period. For more information, see [Real-Time Periods](https://fred.stlouisfed.org/docs/api/fred/realtime_period.html).

        `realtime_end`
        The end of the real-time period. For more information, see [Real-Time Periods](https://fred.stlouisfed.org/docs/api/fred/realtime_period.html).

        ## Description
        https://fred.stlouisfed.org/docs/api/fred/series_release.html

        Get the release for an economic data series.

        ## API Request (HTTPS GET)
        https://api.stlouisfed.org/fred/series/release?series_id=IRA&api_key=abcdefghijklmnopqrstuvwxyz123456&file_type=json

        ## API Response
        ```json
        {
            "realtime_start": "2013-08-14",
            "realtime_end": "2013-08-14",
            "releases": [
                {
                    "id": 21,
                    "realtime_start": "2013-08-14",
                    "realtime_end": "2013-08-14",
                    "name": "H.6 Money Stock Measures",
                    "press_release": true,
                    "link": "http://www.federalreserve.gov/releases/h6/"
                }
            ]
        }
        ```

        ## Returns
        `pandas.DataFrame`

        ## Example
        ```python
        >>> fred = FRED(api_key='abcdefghijklmnopqrstuvwxyz123456')
        >>> fred.series_release(series_id='IRA').head()
               realtime_start realtime_end                      name  press_release                                        link
            id
            21     2022-02-05   2022-02-05  H.6 Money Stock Measures           True  http://www.federalreserve.gov/releases/h6/
        ```
        """

        if realtime_start is not None and realtime_start < date(1776, 7, 4):
            raise ValueError('Variable realtime_start ("{}") is before min date 1776-07-04.'.format(realtime_start))

        if realtime_start is not None and realtime_end is not None and realtime_start > realtime_end:
            raise ValueError('The date set by variable realtime_start ("{}") can not be after the date set by variable realtime_end ("{}").'.format(realtime_start, realtime_end))

        df = pd.DataFrame(
            self._client.get(
                '/fred/series/release',
                'releases',
                series_id=series_id,
                realtime_start=realtime_start,
                realtime_end=realtime_end,
            )
        )

        date_columns = ['realtime_start', 'realtime_end']

        if not df.empty:
            df[date_columns] = df[date_columns].apply(pd.to_datetime, format='%Y-%m-%d')

            df = df.astype(dtype={
                'name': 'string',
                'link': 'string',
                'press_release': 'bool'
            }).set_index('id')

        return df

    def series_search(
            self,
            search_text: str,
            search_type: enums.SearchType = enums.SearchType.full_text,
            realtime_start: date = None,
            realtime_end: date = None,
            order_by: enums.OrderBy = None,
            sort_order: enums.SortOrder = None,
            filter_variable: enums.FilterVariable = None,
            filter_value: enums.FilterValue = None,
            tag_names: List[str] = None,
            exclude_tag_names: List[str] = None
    ) -> pd.DataFrame:
        """
        ## Parameters
        `search_text`
        The words to match against economic data series.

        `search_type`
        Determines the type of search to perform.

        `realtime_start`
        The start of the real-time period. For more information, see [Real-Time Periods](https://fred.stlouisfed.org/docs/api/fred/realtime_period.html).

        `realtime_end`
        The end of the real-time period. For more information, see [Real-Time Periods](https://fred.stlouisfed.org/docs/api/fred/realtime_period.html).

        `order_by`
        Order results by values of the specified attribute.

        `sort_order`
        Sort results is ascending or descending order for attribute values specified by order_by.

        `filter_variable`
        The attribute to filter results by.

        `filter_value`
        The value of the filter_variable attribute to filter results by.

        `tag_names`
        A semicolon delimited list of tag names that series match all of.

        `exclude_tag_names`
        A semicolon delimited list of tag names that series match none of.

        ## Description
        https://fred.stlouisfed.org/docs/api/fred/series_search.html

        Get economic data series that match search text.

        ## API Request (HTTPS GET)
        https://api.stlouisfed.org/fred/series/search?search_text=monetary+service+index&api_key=abcdefghijklmnopqrstuvwxyz123456&file_type=json

        ## API Response
        ```json
        {
          "realtime_start": "2017-08-01",
          "realtime_end": "2017-08-01",
          "order_by": "search_rank",
          "sort_order": "desc",
          "count": 32,
          "offset": 0,
          "limit": 1000,
          "seriess": [
                {
                  "id": "MSIM2",
                  "realtime_start": "2017-08-01",
                  "realtime_end": "2017-08-01",
                  "title": "Monetary Services Index: M2 (preferred)",
                  "observation_start": "1967-01-01",
                  "observation_end": "2013-12-01",
                  "frequency": "Monthly",
                  "frequency_short": "M",
                  "units": "Billions of Dollars",
                  "units_short": "Bil. of $",
                  "seasonal_adjustment": "Seasonally Adjusted",
                  "seasonal_adjustment_short": "SA",
                  "last_updated": "2014-01-17 07:16:44-06",
                  "popularity": 34,
                  "group_popularity": 33,
                  "notes": "The MSI measure the flow of monetary services received each period by households and firms from their holdings of monetary assets (levels of the indexes are sometimes referred to as Divisia monetary aggregates).\\nPreferred benchmark rate equals 100 basis points plus the largest rate in the set of rates.\\nAlternative benchmark rate equals the larger of the preferred benchmark rate and the Baa corporate bond yield.\\nMore information about the new MSI can be found at\\nhttp://research.stlouisfed.org/msi/index.html."
                },
                ...
            ]
        }
        ```

        ## Returns
        `pandas.DataFrame`

        ## Example
        ```python
        >>> fred = FRED(api_key='abcdefghijklmnopqrstuvwxyz123456')
        >>> fred.series_search(search_text='monetary service index').head()
                    realtime_start realtime_end                                            title observation_start observation_end frequency frequency_short                units units_short  seasonal_adjustment seasonal_adjustment_short              last_updated  popularity  group_popularity                                              notes
            id
            MSIMZMP     2022-02-05   2022-02-05         Monetary Services Index: MZM (preferred)        1967-01-01      2013-12-01   Monthly               M  Billions of Dollars   Bil. of $  Seasonally Adjusted                        SA 2014-01-17 13:16:42+00:00          20                20  The MSI measure the flow of monetary services ...
            MSIM2       2022-02-05   2022-02-05          Monetary Services Index: M2 (preferred)        1967-01-01      2013-12-01   Monthly               M  Billions of Dollars   Bil. of $  Seasonally Adjusted                        SA 2014-01-17 13:16:44+00:00          16                16  The MSI measure the flow of monetary services ...
            MSIALLP     2022-02-05   2022-02-05  Monetary Services Index: ALL Assets (preferred)        1967-01-01      2013-12-01   Monthly               M  Billions of Dollars   Bil. of $  Seasonally Adjusted                        SA 2014-01-17 13:16:45+00:00          14                14  The MSI measure the flow of monetary services ...
            MSIM1P      2022-02-05   2022-02-05          Monetary Services Index: M1 (preferred)        1967-01-01      2013-12-01   Monthly               M  Billions of Dollars   Bil. of $  Seasonally Adjusted                        SA 2014-01-17 13:16:45+00:00           9                 9  The MSI measure the flow of monetary services ...
            MSIM2A      2022-02-05   2022-02-05        Monetary Services Index: M2 (alternative)        1967-01-01      2013-12-01   Monthly               M  Billions of Dollars   Bil. of $  Seasonally Adjusted                        SA 2014-01-17 13:16:44+00:00           8                 8  The MSI measure the flow of monetary services ...
        ```
        """

        allowed_orders = [
            enums.OrderBy.search_rank,
            enums.OrderBy.series_id,
            enums.OrderBy.title,
            enums.OrderBy.units,
            enums.OrderBy.frequency,
            enums.OrderBy.seasonal_adjustment,
            enums.OrderBy.realtime_start,
            enums.OrderBy.realtime_end,
            enums.OrderBy.last_updated,
            enums.OrderBy.observation_start,
            enums.OrderBy.observation_end,
            enums.OrderBy.popularity,
            enums.OrderBy.group_popularity
        ]

        # If the value of search_type is 'full_text' then the default value of order_by is 'search_rank'.
        if search_type == enums.SearchType.full_text and order_by is None:
            order_by = enums.OrderBy.search_rank
        # If the value of search_type is 'series_id' then the default value of order_by is 'series_id'.
        elif search_text == enums.SearchType.series_id and order_by is None:
            order_by = enums.OrderBy.series_id

        # If order_by is equal to 'search_rank' or 'popularity', then the default value of sort_order is 'desc'. Otherwise, the default sort order is 'asc'.
        if order_by == enums.OrderBy.search_rank or order_by == enums.OrderBy.popularity and sort_order is None:
            sort_order = enums.SortOrder.desc
        else:
            sort_order = enums.SortOrder.asc

        if order_by not in allowed_orders:
            raise ValueError('Variable order_by ({}) is not one of the values: {}'.format(order_by, ', '.join(map(str, allowed_orders))))

        if search_type not in enums.SearchType:
            raise ValueError('Variable search_type ({}) is not one of the values: {}'.format(search_type, ', '.join(map(str, enums.SearchType))))

        if filter_variable is not None and filter_variable not in enums.FilterVariable:
            raise ValueError('Variable filter_variable ({}) is not one of the values: {}'.format(filter_variable, ', '.join(map(str, enums.FilterVariable))))

        if realtime_start is not None and realtime_start < date(1776, 7, 4):
            raise ValueError('Variable realtime_start ("{}") is before min date 1776-07-04.'.format(realtime_start))

        if realtime_start is not None and realtime_end is not None and realtime_start > realtime_end:
            raise ValueError('The date set by variable realtime_start ("{}") can not be after the date set by variable realtime_end ("{}").'.format(realtime_start, realtime_end))

        df = pd.DataFrame(
            self._client.get(
                '/fred/series/search',
                'seriess',
                limit=1000,
                search_text=search_text,
                search_type=search_type,
                realtime_start=realtime_start,
                realtime_end=realtime_end,
                order_by=order_by,
                sort_order=sort_order,
                filter_variable=filter_variable,
                filter_value=filter_value,
                tag_names=tag_names,
                exclude_tag_names=exclude_tag_names
            )
        )

        date_columns = [
            'realtime_start', 'realtime_end',
            'observation_start', 'observation_end',
        ]

        if not df.empty:
            df[date_columns] = df[date_columns].apply(pd.to_datetime, format='%Y-%m-%d')
            df.last_updated = pd.to_datetime(df.last_updated + '00', utc=True, format='%Y-%m-%d %H:%M:%S%z')

            df = df.astype(dtype={
                'id': 'string',
                'title': 'string',
                'notes': 'string',
                'frequency': 'category',
                'frequency_short': 'category',
                'units_short': 'category',
                'units': 'category',
                'seasonal_adjustment': 'category',
                'seasonal_adjustment_short': 'category'
            }).set_index('id')

        return df

    def series_search_tags(
            self,
            series_search_text: str,
            realtime_start: date = None,
            realtime_end: date = None,
            tag_names: List[str] = None,
            tag_group_id: enums.TagGroupID = None,
            tag_search_text: str = None,
            order_by: enums.OrderBy = enums.OrderBy.series_count,
            sort_order: enums.SortOrder = enums.SortOrder.asc
    ) -> pd.DataFrame:
        """
        ## Parameters
        `series_search_text`
        The words to match against economic data series.

        `realtime_start`
        The start of the real-time period. For more information, see [Real-Time Periods](https://fred.stlouisfed.org/docs/api/fred/realtime_period.html).

        `realtime_end`
        The end of the real-time period. For more information, see [Real-Time Periods](https://fred.stlouisfed.org/docs/api/fred/realtime_period.html).

        `tag_names`
        A semicolon delimited list of tag names to only include in the response. See the related request fred/series/search/related_tags.

        `tag_group_id`
        A tag group id to filter tags by type.

        `tag_search_text`
        The words to find matching tags with.

        `order_by`
        Order results by values of the specified attribute.

        `sort_order`
        Sort results is ascending or descending order for attribute values specified by order_by.

        ## Description
        https://fred.stlouisfed.org/docs/api/fred/series_search_tags.html

        Get the FRED tags for a series search. Optionally, filter results by tag name, tag group, or tag search. See the related request fred/series/search/related_tags.

        ## API Request (HTTPS GET)
        https://api.stlouisfed.org/fred/series/search/tags?series_search_text=monetary+service+index&api_key=abcdefghijklmnopqrstuvwxyz123456&file_type=json

        ## API Response
        ```json
        {
            "realtime_start": "2013-08-14",
            "realtime_end": "2013-08-14",
            "order_by": "series_count",
            "sort_order": "desc",
            "count": 18,
            "offset": 0,
            "limit": 1000,
            "tags": [
                {
                    "name": "academic data",
                    "group_id": "gen",
                    "notes": "Time series data created mainly by academia to address growing demand in understanding specific concerns in the economy that are not well modeled by ordinary statistical agencies.",
                    "created": "2012-08-29 10:22:19-05",
                    "popularity": 62,
                    "series_count": 25
                },
                ...
            ]
        }
        ```

        ## Returns
        `pandas.DataFrame`

        ## Example
        ```python
        >>> fred = FRED(api_key='abcdefghijklmnopqrstuvwxyz123456')
        >>> fred.series_search_tags(series_search_text='monetary service index').head()
                          group_id            notes                   created  popularity  series_count
            name
            accounting         gen                  2012-02-27 16:18:19+00:00          43             2
            advertisement      gen                  2012-08-06 19:50:07+00:00          17             2
            assets             gen                  2012-02-27 16:18:19+00:00          64             2
            boe                src  Bank of England 2013-02-25 22:21:19+00:00          42             2
            communication      gen                  2012-02-27 16:18:19+00:00          22             2
        ```
        """
        allowed_orders = [
            enums.OrderBy.series_count,
            enums.OrderBy.popularity,
            enums.OrderBy.created,
            enums.OrderBy.name,
            enums.OrderBy.group_id,
        ]

        if order_by not in allowed_orders:
            raise ValueError('Variable order_by ({}) is not one of the values: {}'.format(order_by, ', '.join(map(str, allowed_orders))))

        if realtime_start is not None and realtime_start < date(1776, 7, 4):
            raise ValueError('Variable realtime_start ("{}") is before min date 1776-07-04.'.format(realtime_start))

        if realtime_start is not None and realtime_end is not None and realtime_start > realtime_end:
            raise ValueError('The date set by variable realtime_start ("{}") can not be after the date set by variable realtime_end ("{}").'.format(realtime_start, realtime_end))

        df = pd.DataFrame(
            self._client.get(
                '/fred/series/search/tags',
                'tags',
                limit=1000,
                series_search_text=series_search_text,
                realtime_start=realtime_start,
                realtime_end=realtime_end,
                tag_names=tag_names,
                tag_group_id=tag_group_id,
                tag_search_text=tag_search_text,
                order_by=order_by,
                sort_order=sort_order
            )
        )

        if not df.empty:
            df.created = pd.to_datetime(df.created + '00', utc=True, format='%Y-%m-%d %H:%M:%S%z')

            df = df.astype(dtype={
                'name': 'string',
                'notes': 'string',
                'group_id': 'category'
            }).set_index('name')

        return df

    def series_search_related_tags(
            self,
            series_search_text: str,
            realtime_start: date = None,
            realtime_end: date = None,
            tag_names: List[str] = None,
            exclude_tag_names: List[str] = None,
            tag_group_id: enums.TagGroupID = None,
            tag_search_text: str = None,
            order_by: enums.OrderBy = enums.OrderBy.series_count,
            sort_order: enums.SortOrder = enums.SortOrder.asc
    ) -> pd.DataFrame:
        """
        ## Parameters
        `series_search_text`
        The words to match against economic data series.

        `realtime_start`
        The start of the real-time period. For more information, see [Real-Time Periods](https://fred.stlouisfed.org/docs/api/fred/realtime_period.html).

        `realtime_end`
        The end of the real-time period. For more information, see [Real-Time Periods](https://fred.stlouisfed.org/docs/api/fred/realtime_period.html).

        `tag_names`
        A semicolon delimited list of tag names to only include in the response. See the related request fred/series/search/related_tags.

        `exclude_tag_names`
        Tuple of tag names that series match none of.

        `tag_group_id`
        A tag group id to filter tags by type.

        `tag_search_text`
        The words to find matching tags with.

        `order_by`
        Order results by values of the specified attribute.

        `sort_order`
        Sort results is ascending or descending order for attribute values specified by order_by.

        ## Description
        https://fred.stlouisfed.org/docs/api/fred/series_search_related_tags.html

        Get the related FRED tags for one or more FRED tags matching a series search. Optionally, filter results by tag group or tag search.
        FRED tags are attributes assigned to series.
        For this request, related FRED tags are the tags assigned to series that match all tags in the tag_names parameter, no tags in the exclude_tag_names parameter,
        and the search words set by the series_search_text parameter.
        See the related request fred/series/search/tags.

        ## API Request (HTTPS GET)
        https://api.stlouisfed.org/fred/series/search/related_tags?series_search_text=mortgage+rate&tag_names=30-year;frb&api_key=abcdefghijklmnopqrstuvwxyz123456&file_type=json

        ## API Response
        ```json
        {
            "realtime_start": "2013-08-14",
            "realtime_end": "2013-08-14",
            "order_by": "series_count",
            "sort_order": "desc",
            "count": 10,
            "offset": 0,
            "limit": 1000,
            "tags": [
                {
                    "name": "conventional",
                    "group_id": "gen",
                    "notes": "",
                    "created": "2012-02-27 10:18:19-06",
                    "popularity": 63,
                    "series_count": 3
                },
                ...
            ]
        }
        ```

        ## Returns
        `pandas.DataFrame`

        ## Example
        ```python
        >>> fred = FRED(api_key='abcdefghijklmnopqrstuvwxyz123456')
        >>> fred.series_search_related_tags(series_search_text='mortgage rate', tag_names=['30-year', 'frb'], realtime_start=date(2022, 1, 5), realtime_end=date(2022, 1, 5)).head()
                          group_id                         notes                   created  popularity  series_count
            name
            conventional       gen                               2012-02-27 16:18:19+00:00          21             2
            discontinued       gen                               2012-02-27 16:18:19+00:00          67             2
            h15                rls  H.15 Selected Interest Rates 2012-08-16 20:21:17+00:00          57             2
            interest           gen                               2012-02-27 16:18:19+00:00          74             2
            interest rate      gen                               2012-05-29 15:14:19+00:00          74             2
        """

        allowed_orders = [
            enums.OrderBy.series_count,
            enums.OrderBy.popularity,
            enums.OrderBy.created,
            enums.OrderBy.name,
            enums.OrderBy.group_id,
        ]

        if order_by not in allowed_orders:
            raise ValueError('Variable order_by ({}) is not one of the values: {}'.format(order_by, ', '.join(map(str, allowed_orders))))

        if realtime_start is not None and realtime_start < date(1776, 7, 4):
            raise ValueError('Variable realtime_start ("{}") is before min date 1776-07-04.'.format(realtime_start))

        if realtime_start is not None and realtime_end is not None and realtime_start > realtime_end:
            raise ValueError('The date set by variable realtime_start ("{}") can not be after the date set by variable realtime_end ("{}").'.format(realtime_start, realtime_end))

        df = pd.DataFrame(
            self._client.get(
                '/fred/series/search/related_tags',
                'tags',
                limit=1000,
                series_search_text=series_search_text,
                realtime_start=realtime_start,
                realtime_end=realtime_end,
                tag_names=tag_names,
                exclude_tag_names=exclude_tag_names,
                tag_group_id=tag_group_id,
                tag_search_text=tag_search_text,
                order_by=order_by,
                sort_order=sort_order
            )
        )

        if not df.empty:
            df.created = pd.to_datetime(df.created + '00', utc=True, format='%Y-%m-%d %H:%M:%S%z')

            df = df.astype(dtype={
                'name': 'string',
                'notes': 'string',
                'group_id': 'category'
            }).set_index('name')

        return df

    def series_tags(
            self,
            series_id: str,
            realtime_start: date = None,
            realtime_end: date = None,
            order_by: enums.OrderBy = enums.OrderBy.series_count,
            sort_order: enums.SortOrder = enums.SortOrder.asc
    ) -> pd.DataFrame:
        """
        ## Parameters
        `series_id`
        The id for a series.

        `realtime_start`
        The start of the real-time period. For more information, see [Real-Time Periods](https://fred.stlouisfed.org/docs/api/fred/realtime_period.html).

        `realtime_end`
        The end of the real-time period. For more information, see [Real-Time Periods](https://fred.stlouisfed.org/docs/api/fred/realtime_period.html).

        `order_by`
        Order results by values of the specified attribute.

        `sort_order`
        Sort results is ascending or descending order for attribute values specified by order_by.

        ## Description
        https://fred.stlouisfed.org/docs/api/fred/series_tags.html

        Get the FRED tags for a series.

        ## API Request (HTTPS GET)
        https://api.stlouisfed.org/fred/series/tags?series_id=STLFSI&api_key=abcdefghijklmnopqrstuvwxyz123456&file_type=json

        ## API Response
        ```json
        {
            "realtime_start": "2013-08-14",
            "realtime_end": "2013-08-14",
            "order_by": "series_count",
            "sort_order": "desc",
            "count": 8,
            "offset": 0,
            "limit": 1000,
            "tags": [
                {
                    "name": "nation",
                    "group_id": "geot",
                    "notes": "Country Level",
                    "created": "2012-02-27 10:18:19-06",
                    "popularity": 100,
                    "series_count": 105200
                },
                ...
            ]
        }
        ```

        ## Returns
        `pandas.DataFrame`

        ## Example
        ```python
        >>> fred = FRED(api_key='abcdefghijklmnopqrstuvwxyz123456')
        >>> fred.series_tags(series_id='STLFSI').head()
                         group_id                             notes                   created  popularity  series_count
            name
            stlfsi            rls  St. Louis Financial Stress Index 2012-08-16 20:21:17+00:00          19             4
            fsi               gen            Financial Stress Index 2014-08-08 19:01:37+00:00          26            26
            weekly           freq                                   2012-02-27 16:18:19+00:00          68          3548
            financial         gen                                   2012-02-27 16:18:19+00:00          55         21652
            discontinued      gen                                   2012-02-27 16:18:19+00:00          67         40386
        """

        allowed_orders = [
            enums.OrderBy.series_count,
            enums.OrderBy.popularity,
            enums.OrderBy.created,
            enums.OrderBy.name,
            enums.OrderBy.group_id,
        ]

        if order_by not in allowed_orders:
            raise ValueError('Variable order_by ({}) is not one of the values: {}'.format(order_by, ', '.join(map(str, allowed_orders))))

        if realtime_start is not None and realtime_start < date(1776, 7, 4):
            raise ValueError('Variable realtime_start ("{}") is before min date 1776-07-04.'.format(realtime_start))

        if realtime_start is not None and realtime_end is not None and realtime_start > realtime_end:
            raise ValueError('The date set by variable realtime_start ("{}") can not be after the date set by variable realtime_end ("{}").'.format(realtime_start, realtime_end))

        df = pd.DataFrame(
            self._client.get(
                '/fred/series/tags',
                'tags',
                series_id=series_id,
                realtime_start=realtime_start,
                realtime_end=realtime_end,
                order_by=order_by,
                sort_order=sort_order
            )
        )

        if not df.empty:
            df.created = pd.to_datetime(df.created + '00', utc=True, format='%Y-%m-%d %H:%M:%S%z')

            df = df.astype(dtype={
                'name': 'string',
                'notes': 'string',
                'group_id': 'category'
            }).set_index('name')

        return df

    def series_updates(
            self,
            realtime_start: date = None,
            realtime_end: date = None,
            filter_value: enums.FilterValue = enums.FilterValue.all,
            start_time: datetime = None,
            end_time: datetime = None
    ) -> pd.DataFrame:
        """
        ## Parameters

        `realtime_start`
        The start of the real-time period. For more information, see [Real-Time Periods](https://fred.stlouisfed.org/docs/api/fred/realtime_period.html).

        `realtime_end`
        The end of the real-time period. For more information, see [Real-Time Periods](https://fred.stlouisfed.org/docs/api/fred/realtime_period.html).

        `filter_value`
        Limit results by geographic type of economic data series; namely 'macro', 'regional', and 'all'.

        `start_time`
        Start time for limiting results for a time range, can filter down to minutes

        `end_time`
        End time for limiting results for a time range, can filter down to minutes

        ## Description
        https://fred.stlouisfed.org/docs/api/fred/series_updates.html

        Get economic data series sorted by when observations were updated on the FRED server (attribute last_updated).
        Results are limited to series updated within the last two weeks.

        ## API Request (HTTPS GET)
        https://api.stlouisfed.org/fred/series/updates?api_key=abcdefghijklmnopqrstuvwxyz123456&file_type=json

        ## API Response
        ```json
        {
            "realtime_start": "2013-08-14",
            "realtime_end": "2013-08-14",
            "filter_variable": "geography",
            "filter_value": "all",
            "order_by": "last_updated",
            "sort_order": "desc",
            "count": 143535,
            "offset": 0,
            "limit": 100,
            "seriess": [
                {
                    "id": "PPIITM",
                    "realtime_start": "2013-08-14",
                    "realtime_end": "2013-08-14",
                    "title": "Producer Price Index: Intermediate Materials: Supplies & Components",
                    "observation_start": "1947-04-01",
                    "observation_end": "2013-07-01",
                    "frequency": "Monthly",
                    "frequency_short": "M",
                    "units": "Index 1982=100",
                    "units_short": "Index 1982=100",
                    "seasonal_adjustment": "Seasonally Adjusted",
                    "seasonal_adjustment_short": "SA",
                    "last_updated": "2013-08-14 08:36:05-05",
                    "popularity": 52
                },
                ...
            ]
        }
        ```

        ## Returns
        `pandas.DataFrame`

        ## Example
        ```python
        >>> fred = FRED(api_key='abcdefghijklmnopqrstuvwxyz123456')
        >>> fred.series_updates(start_time=datetime(2022, 1, 15), end_time=datetime(2022, 1, 16)).head()
                     realtime_start realtime_end                  title observation_start observation_end     frequency frequency_short         units units_short      seasonal_adjustment seasonal_adjustment_short              last_updated  popularity                                              notes
            id
            SP500        2022-02-05   2022-02-05                S&P 500        2012-02-06      2022-02-04  Daily, Close               D         Index       Index  Not Seasonally Adjusted                       NSA 2022-02-05 01:11:04+00:00          85  The observations for the S&P 500 represent the...
            CBBCHUSD     2022-02-05   2022-02-05  Coinbase Bitcoin Cash        2017-12-20      2022-02-04  Daily, 7-Day               D  U.S. Dollars      U.S. $  Not Seasonally Adjusted                       NSA 2022-02-05 01:04:07+00:00          22  All data is as of 5 PM PST.
            CBBTCUSD     2022-02-05   2022-02-05       Coinbase Bitcoin        2014-12-01      2022-02-04  Daily, 7-Day               D  U.S. Dollars      U.S. $  Not Seasonally Adjusted                       NSA 2022-02-05 01:04:06+00:00          65  All data is as of 5 PM PST.
            CBETHUSD     2022-02-05   2022-02-05      Coinbase Ethereum        2016-05-18      2022-02-04  Daily, 7-Day               D  U.S. Dollars      U.S. $  Not Seasonally Adjusted                       NSA 2022-02-05 01:04:05+00:00          44  All data is as of 5 PM PST.
            CBLTCUSD     2022-02-05   2022-02-05      Coinbase Litecoin        2016-08-17      2022-02-04  Daily, 7-Day               D  U.S. Dollars      U.S. $  Not Seasonally Adjusted                       NSA 2022-02-05 01:04:03+00:00          20  All data is as of 5 PM PST.
        ```
        """

        if filter_value not in enums.FilterValue:
            raise ValueError('Variable filter_value ({}) is not one of the values: {}'.format(filter_value, ', '.join(map(str, enums.FilterValue))))

        if start_time is not None and end_time is None:
            raise ValueError('end_time is required if start_time is set')

        if end_time is not None and start_time is None:
            raise ValueError('start_time is required if end_time is set')

        if start_time is not None and end_time is not None and start_time >= end_time:
            raise ValueError('end_time must be greater than start_time')

        if realtime_start is not None and realtime_start < date(1776, 7, 4):
            raise ValueError('Variable realtime_start ("{}") is before min date 1776-07-04.'.format(realtime_start))

        if realtime_start is not None and realtime_end is not None and realtime_start > realtime_end:
            raise ValueError('The date set by variable realtime_start ("{}") can not be after the date set by variable realtime_end ("{}").'.format(realtime_start, realtime_end))

        df = pd.DataFrame(
            self._client.get(
                '/fred/series/updates',
                'seriess',
                limit=1000,
                realtime_start=realtime_start,
                realtime_end=realtime_end,
                filter_value=filter_value,
                start_time=start_time,
                end_time=end_time
            )
        )

        date_columns = [
            'realtime_start', 'realtime_end',
            'observation_start', 'observation_end'
        ]

        if not df.empty:
            df[date_columns] = df[date_columns].apply(pd.to_datetime, format='%Y-%m-%d')
            df.last_updated = pd.to_datetime(df.last_updated + '00', utc=True, format='%Y-%m-%d %H:%M:%S%z')

            df = df.astype(dtype={
                'id': 'string',
                'notes': 'string',
                'title': 'string',
                'seasonal_adjustment': 'category',
                'seasonal_adjustment_short': 'category',
                'units': 'category',
                'units_short': 'category',
                'frequency': 'category',
                'frequency_short': 'category',
            }).set_index('id')

        return df

    def series_vintagedates(
            self,
            series_id: str,
            realtime_start: date = date(1776, 7, 4),
            realtime_end: date = date(9999, 12, 31),
            sort_order: enums.SortOrder = enums.SortOrder.asc
    ) -> pd.Series:
        """
        ## Parameters
        `series_id`
        The id for a series.

        `realtime_start`
        The start of the real-time period. For more information, see [Real-Time Periods](https://fred.stlouisfed.org/docs/api/fred/realtime_period.html).

        `realtime_end`
        The end of the real-time period. For more information, see [Real-Time Periods](https://fred.stlouisfed.org/docs/api/fred/realtime_period.html).

        `sort_order`
        Sort results is ascending or descending order for attribute values specified by order_by.

        ## Description
        https://fred.stlouisfed.org/docs/api/fred/series_vintagedates.html

        Get the dates in history when a series' data values were revised or new data values were released.
        Vintage dates are the release dates for a series excluding release dates when the data for the series did not change.

        ## API Request (HTTPS GET)
        https://api.stlouisfed.org/fred/series/vintagedates?series_id=GNPCA&api_key=abcdefghijklmnopqrstuvwxyz123456&file_type=json

        ## API Response
        ```json
        {
            "realtime_start": "1776-07-04",
            "realtime_end": "9999-12-31",
            "order_by": "vintage_date",
            "sort_order": "asc",
            "count": 162,
            "offset": 0,
            "limit": 10000,
            "vintage_dates": [
                "1958-12-21",
                "1959-02-19",
                ...
            ]
        }
        ```

        ## Returns
        `pandas.Series`

        ## Example
        ```python
        >>> fred = FRED(api_key='abcdefghijklmnopqrstuvwxyz123456')
        >>> fred.series_vintagedates(series_id='GNPCA').head()
            0    1958-12-21
            1    1959-02-19
            2    1959-07-19
            3    1960-02-16
            4    1960-07-22
        ```
        """

        if realtime_start is not None and realtime_start < date(1776, 7, 4):
            raise ValueError('Variable realtime_start ("{}") is before min date 1776-07-04.'.format(realtime_start))

        if realtime_start > realtime_end:
            raise ValueError('The date set by variable realtime_start ("{}") can not be after the date set by variable realtime_end ("{}").'.format(realtime_start, realtime_end))

        return pd.to_datetime(
            pd.Series(
                self._client.get(
                    '/fred/series/vintagedates',
                    'vintage_dates',
                    limit=10000,
                    series_id=series_id,
                    realtime_start=realtime_start,
                    realtime_end=realtime_end,
                    sort_order=sort_order
                )
            ), format='%Y-%m-%d'
        )

    """
    Sources

    https://fred.stlouisfed.org/sources
    """

    def sources(
            self,
            realtime_start: date = None,
            realtime_end: date = None,
            order_by: enums.OrderBy = enums.OrderBy.source_id,
            sort_order: enums.SortOrder = enums.SortOrder.asc
    ) -> pd.DataFrame:
        """
        ## Parameters
        `realtime_start`
        The start of the real-time period. For more information, see [Real-Time Periods](https://fred.stlouisfed.org/docs/api/fred/realtime_period.html).

        `realtime_end`
        The end of the real-time period. For more information, see [Real-Time Periods](https://fred.stlouisfed.org/docs/api/fred/realtime_period.html).

        `order_by`
        Order results by values of the specified attribute.

        `sort_order`
        Sort results is ascending or descending order for attribute values specified by order_by.

        ## Description
        https://fred.stlouisfed.org/docs/api/fred/sources.html

        Get all sources of economic data.

        ## API Request (HTTPS GET)
        https://api.stlouisfed.org/fred/sources?api_key=abcdefghijklmnopqrstuvwxyz123456&file_type=json

        ## API Response
        ```json
        {
            "realtime_start": "2013-08-14",
            "realtime_end": "2013-08-14",
            "order_by": "source_id",
            "sort_order": "asc",
            "count": 58,
            "offset": 0,
            "limit": 1000,
            "sources": [
                {
                    "id": 1,
                    "realtime_start": "2013-08-14",
                    "realtime_end": "2013-08-14",
                    "name": "Board of Governors of the Federal Reserve System",
                    "link": "http://www.federalreserve.gov/"
                },
                ...
            ]
        }
        ```

        ## Returns
        `pandas.DataFrame`

        ## Example
        ```python
        >>> fred = FRED(api_key='abcdefghijklmnopqrstuvwxyz123456')
        >>> fred.sources()
               realtime_start realtime_end                                               name                              link notes
            id
            1      2022-02-05   2022-02-05  Board of Governors of the Federal Reserve Syst...    http://www.federalreserve.gov/  <NA>
            3      2022-02-05   2022-02-05               Federal Reserve Bank of Philadelphia  https://www.philadelphiafed.org/  <NA>
            4      2022-02-05   2022-02-05                  Federal Reserve Bank of St. Louis        http://www.stlouisfed.org/  <NA>
            6      2022-02-05   2022-02-05  Federal Financial Institutions Examination Cou...             http://www.ffiec.gov/  <NA>
            11     2022-02-05   2022-02-05                                Dow Jones & Company           http://www.dowjones.com  <NA>
        ```
        """

        allowed_orders = [
            enums.OrderBy.source_id,
            enums.OrderBy.name,
            enums.OrderBy.realtime_start,
            enums.OrderBy.realtime_end
        ]

        if order_by not in allowed_orders:
            raise ValueError('Variable order_by ({}) is not one of the values: {}'.format(order_by, ', '.join(map(str, allowed_orders))))

        if realtime_start is not None and realtime_start < date(1776, 7, 4):
            raise ValueError('Variable realtime_start ("{}") is before min date 1776-07-04.'.format(realtime_start))

        if realtime_start is not None and realtime_end is not None and realtime_start > realtime_end:
            raise ValueError('The date set by variable realtime_start ("{}") can not be after the date set by variable realtime_end ("{}").'.format(realtime_start, realtime_end))

        df = pd.DataFrame(
            self._client.get(
                '/fred/sources',
                'sources',
                limit=1000,
                realtime_start=realtime_start,
                realtime_end=realtime_end,
                order_by=order_by,
                sort_order=sort_order
            )
        )

        date_columns = ['realtime_start', 'realtime_end']

        if not df.empty:
            df[date_columns] = df[date_columns].apply(pd.to_datetime, format='%Y-%m-%d')
            df = df.astype(dtype={
                'name': 'string',
                'notes': 'string',
                'link': 'string'
            }).set_index('id')

        return df

    def source(self, source_id: int, realtime_start: date = None, realtime_end: date = None) -> models.Source:
        """
        ## Parameters
        `source_id`
        The id for a source.

        `realtime_start`
        The start of the real-time period. For more information, see [Real-Time Periods](https://fred.stlouisfed.org/docs/api/fred/realtime_period.html).

        `realtime_end`
        The end of the real-time period. For more information, see [Real-Time Periods](https://fred.stlouisfed.org/docs/api/fred/realtime_period.html).

        ## Description
        https://fred.stlouisfed.org/docs/api/fred/source.html

        Get a source of economic data.

        ## API Request (HTTPS GET)
        https://api.stlouisfed.org/fred/source?source_id=1&api_key=abcdefghijklmnopqrstuvwxyz123456&file_type=json

        ## API Response
        ```json
        {
            "realtime_start": "2013-08-14",
            "realtime_end": "2013-08-14",
            "sources": [
                {
                    "id": 1,
                    "realtime_start": "2013-08-14",
                    "realtime_end": "2013-08-14",
                    "name": "Board of Governors of the Federal Reserve System",
                    "link": "http://www.federalreserve.gov/"
                }
            ]
        }
        ```

        ## Returns
        `pystlouisfed.models.Source`

        ## Example
        ```python
        >>> fred = FRED(api_key='abcdefghijklmnopqrstuvwxyz123456')
        >>> fred.source(source_id=1)
            Source(id=1, realtime_start='2022-01-14', realtime_end='2022-01-14', name='Board of Governors of the Federal Reserve System (US)', link='http://www.federalreserve.gov/')
        ```
        """

        if realtime_start is not None and realtime_start < date(1776, 7, 4):
            raise ValueError('Variable realtime_start ("{}") is before min date 1776-07-04.'.format(realtime_start))

        if realtime_start is not None and realtime_end is not None and realtime_start > realtime_end:
            raise ValueError('The date set by variable realtime_start ("{}") can not be after the date set by variable realtime_end ("{}").'.format(realtime_start, realtime_end))

        data = self._client.get(
            '/fred/source',
            'sources',
            source_id=source_id,
            realtime_start=realtime_start,
            realtime_end=realtime_end
        )

        return models.Source(**data[0])

    def source_releases(
            self,
            source_id: int,
            realtime_start: date = None,
            realtime_end: date = None,
            order_by: enums.OrderBy = enums.OrderBy.release_id,
            sort_order: enums.SortOrder = enums.SortOrder.asc
    ) -> pd.DataFrame:
        """
        ## Parameters
        `source_id`
        The id for a source.

        `realtime_start`
        The start of the real-time period. For more information, see [Real-Time Periods](https://fred.stlouisfed.org/docs/api/fred/realtime_period.html).

        `realtime_end`
        The end of the real-time period. For more information, see [Real-Time Periods](https://fred.stlouisfed.org/docs/api/fred/realtime_period.html).

        `order_by`
        Order results by values of the specified attribute.

        `sort_order`
        Sort results is ascending or descending order for attribute values specified by order_by.

        ## Description
        https://fred.stlouisfed.org/docs/api/fred/source_releases.html

        Get the releases for a source.

        ## API Request (HTTPS GET)
        https://api.stlouisfed.org/fred/source/releases?source_id=1&api_key=abcdefghijklmnopqrstuvwxyz123456&file_type=json

        ## API Response
        ```json
        {
            "realtime_start": "2013-08-14",
            "realtime_end": "2013-08-14",
            "order_by": "release_id",
            "sort_order": "asc",
            "count": 26,
            "offset": 0,
            "limit": 1000,
            "releases": [
                {
                    "id": 13,
                    "realtime_start": "2013-08-14",
                    "realtime_end": "2013-08-14",
                    "name": "G.17 Industrial Production and Capacity Utilization",
                    "press_release": true,
                    "link": "http://www.federalreserve.gov/releases/g17/"
                },
                ...
            ]
        }
        ```

        ## Returns
        `pandas.DataFrame`

        ## Example
        ```python
        >>> fred = FRED(api_key='abcdefghijklmnopqrstuvwxyz123456')
        >>> fred.source_releases(source_id=1).head()
               realtime_start realtime_end                                               name  press_release                                         link notes
            id
            13     2022-02-05   2022-02-05  G.17 Industrial Production and Capacity Utiliz...           True  http://www.federalreserve.gov/releases/g17/  <NA>
            14     2022-02-05   2022-02-05                               G.19 Consumer Credit           True  http://www.federalreserve.gov/releases/g19/  <NA>
            15     2022-02-05   2022-02-05                         G.5 Foreign Exchange Rates           True   http://www.federalreserve.gov/releases/g5/  <NA>
            17     2022-02-05   2022-02-05                        H.10 Foreign Exchange Rates           True  http://www.federalreserve.gov/releases/h10/  <NA>
            18     2022-02-05   2022-02-05                       H.15 Selected Interest Rates           True  http://www.federalreserve.gov/releases/h15/  <NA>
        ```
        """

        allowed_orders = [
            enums.OrderBy.release_id,
            enums.OrderBy.name,
            enums.OrderBy.press_release,
            enums.OrderBy.realtime_start,
            enums.OrderBy.realtime_end
        ]

        if order_by not in allowed_orders:
            raise ValueError('Variable order_by ({}) is not one of the values: {}'.format(order_by, ', '.join(map(str, allowed_orders))))

        if realtime_start is not None and realtime_start < date(1776, 7, 4):
            raise ValueError('Variable realtime_start ("{}") is before min date 1776-07-04.'.format(realtime_start))

        if realtime_start is not None and realtime_end is not None and realtime_start > realtime_end:
            raise ValueError('The date set by variable realtime_start ("{}") can not be after the date set by variable realtime_end ("{}").'.format(realtime_start, realtime_end))

        df = pd.DataFrame(
            self._client.get(
                '/fred/source/releases',
                'releases',
                limit=1000,
                source_id=source_id,
                realtime_start=realtime_start,
                realtime_end=realtime_end,
                order_by=order_by,
                sort_order=sort_order
            )
        )

        date_columns = ['realtime_start', 'realtime_end']

        if not df.empty:
            df[date_columns] = df[date_columns].apply(pd.to_datetime, format='%Y-%m-%d')

            df = df.astype(dtype={
                'name': 'string',
                'link': 'string',
                'notes': 'string',
                'press_release': 'bool'
            }).set_index('id')

        return df

    """
    Tags

    https://fred.stlouisfed.org/tags
    """

    def tags(
            self,
            realtime_start: date = None,
            realtime_end: date = None,
            tag_names: List[str] = None,
            tag_group_id: enums.TagGroupID = None,
            search_text: str = None,
            order_by: enums.OrderBy = enums.OrderBy.series_count,
            sort_order: enums.SortOrder = enums.SortOrder.asc
    ) -> pd.DataFrame:
        """
        ## Parameters
        `realtime_start`
        The start of the real-time period. For more information, see [Real-Time Periods](https://fred.stlouisfed.org/docs/api/fred/realtime_period.html).

        `realtime_end`
        The end of the real-time period. For more information, see [Real-Time Periods](https://fred.stlouisfed.org/docs/api/fred/realtime_period.html).

        `tag_names`
        Tuple of tag names that series match all of.

        `tag_group_id`
        A tag group id to filter tags by type.

        `search_text`
        The words to find matching tags with.

        `order_by`
        Order results by values of the specified attribute.

        `sort_order`
        Sort results is ascending or descending order for attribute values specified by order_by.

        ## Description
        https://fred.stlouisfed.org/docs/api/fred/tags.html

        Get FRED tags. Optionally, filter results by tag name, tag group, or search. FRED tags are attributes assigned to series. See the related request fred/related_tags.

        ## API Request (HTTPS GET)
        https://api.stlouisfed.org/fred/tags?api_key=abcdefghijklmnopqrstuvwxyz123456&file_type=json

        ## API Response
        ```json
        {
            "realtime_start": "2013-08-14",
            "realtime_end": "2013-08-14",
            "order_by": "series_count",
            "sort_order": "desc",
            "count": 4794,
            "offset": 0,
            "limit": 1000,
            "tags": [
                {
                    "name": "nation",
                    "group_id": "geot",
                    "notes": "Country Level",
                    "created": "2012-02-27 10:18:19-06",
                    "popularity": 100,
                    "series_count": 105200
                },
                ...
            ]
        }
        ```

        ## Returns
        `pandas.DataFrame`

        ## Example
        ```python
        >>> fred = FRED(api_key='abcdefghijklmnopqrstuvwxyz123456')
        >>> fred.tags().head()
                           group_id notes                   created  popularity  series_count
            name
            14 years +          gen       2012-08-06 19:40:56+00:00          -6             2
            2-month +           gen       2012-08-06 19:34:05+00:00         -62             2
            2-week              gen       2012-05-25 16:29:34+00:00          -6             2
            30 to 34 years      gen       2013-10-10 21:13:04+00:00         -13             2
            3-family +          gen       2012-08-06 19:48:11+00:00         -49             2
        ```
        """

        allowed_orders = [
            enums.OrderBy.series_count,
            enums.OrderBy.popularity,
            enums.OrderBy.created,
            enums.OrderBy.name,
            enums.OrderBy.group_id
        ]

        if order_by not in allowed_orders:
            raise ValueError('Variable order_by ({}) is not one of the values: {}'.format(order_by, ', '.join(map(str, allowed_orders))))

        if tag_group_id is not None and tag_group_id not in enums.TagGroupID:
            raise ValueError('Variable tag_group_id ({}) is not one of the values: {}'.format(tag_group_id, ', '.join(map(str, enums.TagGroupID))))

        if realtime_start is not None and realtime_start < date(1776, 7, 4):
            raise ValueError('Variable realtime_start ("{}") is before min date 1776-07-04.'.format(realtime_start))

        if realtime_start is not None and realtime_end is not None and realtime_start > realtime_end:
            raise ValueError('The date set by variable realtime_start ("{}") can not be after the date set by variable realtime_end ("{}").'.format(realtime_start, realtime_end))

        df = pd.DataFrame(
            self._client.get(
                '/fred/tags',
                'tags',
                limit=1000,
                realtime_start=realtime_start,
                realtime_end=realtime_end,
                tag_names=tag_names,
                tag_group_id=tag_group_id,
                search_text=search_text,
                order_by=order_by,
                sort_order=sort_order
            )
        )

        if not df.empty:
            df.created = pd.to_datetime(df.created + '00', utc=True, format='%Y-%m-%d %H:%M:%S%z')

            df = df.astype(dtype={
                'name': 'string',
                'notes': 'string',
                'group_id': 'category'
            }).set_index('name')

        return df

    def related_tags(
            self,
            realtime_start: date = None,
            realtime_end: date = None,
            tag_names: List[str] = None,
            exclude_tag_names: List[str] = None,
            tag_group_id: enums.TagGroupID = None,
            search_text: str = None,
            order_by: enums.OrderBy = enums.OrderBy.series_count,
            sort_order: enums.SortOrder = enums.SortOrder.asc
    ) -> pd.DataFrame:
        """
        ## Parameters
        `realtime_start`
        The start of the real-time period. For more information, see [Real-Time Periods](https://fred.stlouisfed.org/docs/api/fred/realtime_period.html).

        `realtime_end`
        The end of the real-time period. For more information, see [Real-Time Periods](https://fred.stlouisfed.org/docs/api/fred/realtime_period.html).

        `tag_names`
        Tuple of tag names that series match all of.

        `exclude_tag_names`
        Tuple of tag names that series match none of.

        `tag_group_id`
        A tag group id to filter tags by type.

        `search_text`
        The words to find matching tags with.

        `order_by`
        Order results by values of the specified attribute.

        `sort_order`
        Sort results is ascending or descending order for attribute values specified by order_by.

        ## Description
        https://fred.stlouisfed.org/docs/api/fred/related_tags.html

        Get the related FRED tags for one or more FRED tags.
        Optionally, filter results by tag group or search.
        FRED tags are attributes assigned to series.
        Related FRED tags are the tags assigned to series that match all tags in the tag_names parameter and no tags in the exclude_tag_names parameter.
        See the related request fred/tags.

        ## API Request (HTTPS GET)
        https://api.stlouisfed.org/fred/related_tags?tag_names=monetary+aggregates;weekly&api_key=abcdefghijklmnopqrstuvwxyz123456&file_type=json

        ## API Response
        ```json
        {
            "realtime_start": "2013-08-14",
            "realtime_end": "2013-08-14",
            "order_by": "series_count",
            "sort_order": "desc",
            "count": 13,
            "offset": 0,
            "limit": 1000,
            "tags": [
                {
                    "name": "nation",
                    "group_id": "geot",
                    "notes": "Country Level",
                    "created": "2012-02-27 10:18:19-06",
                    "popularity": 100,
                    "series_count": 12
                },
                ...
            ]
        }
        ```

        ## Returns
        `pandas.DataFrame`

        ## Example
        ```python
        >>> fred = FRED(api_key='abcdefghijklmnopqrstuvwxyz123456')
        >>> fred.related_tags(tag_names=['monetary aggregates', 'weekly']).head()
                                           group_id           notes                   created  popularity  series_count
            name
            copyrighted: citation required       cc            <NA> 2018-12-18 05:33:13+00:00          88             2
            currency                            gen                 2012-02-27 16:18:19+00:00          62             2
            frb stl                             src   St. Louis Fed 2012-02-27 16:18:19+00:00          68             2
            m1                                  gen  M1 Money Stock 2012-02-27 16:18:19+00:00          47             2
            m3                                  gen  M3 Money Stock 2012-02-27 16:18:19+00:00          39             2
        ```
        """

        allowed_orders = [
            enums.OrderBy.series_count,
            enums.OrderBy.popularity,
            enums.OrderBy.created,
            enums.OrderBy.name,
            enums.OrderBy.group_id
        ]

        allowed_tag_group_ids = [
            enums.TagGroupID.frequency,
            enums.TagGroupID.general_or_concept,
            enums.TagGroupID.geography,
            enums.TagGroupID.geography_type,
            enums.TagGroupID.release,
            enums.TagGroupID.seasonal_adjustment,
            enums.TagGroupID.source
        ]

        if order_by not in allowed_orders:
            raise ValueError('Variable order_by ({}) is not one of the values: {}'.format(order_by, ', '.join(map(str, allowed_orders))))

        if tag_group_id is not None and tag_group_id not in allowed_tag_group_ids:
            raise ValueError('Variable tag_group_id ({}) is not one of the values: {}'.format(tag_group_id, ', '.join(map(str, allowed_tag_group_ids))))

        if realtime_start is not None and realtime_start < date(1776, 7, 4):
            raise ValueError('Variable realtime_start ("{}") is before min date 1776-07-04.'.format(realtime_start))

        if realtime_start is not None and realtime_end is not None and realtime_start > realtime_end:
            raise ValueError('The date set by variable realtime_start ("{}") can not be after the date set by variable realtime_end ("{}").'.format(realtime_start, realtime_end))

        df = pd.DataFrame(
            self._client.get(
                '/fred/related_tags',
                'tags',
                limit=1000,
                realtime_start=realtime_start,
                realtime_end=realtime_end,
                tag_names=tag_names,
                exclude_tag_names=exclude_tag_names,
                tag_group_id=tag_group_id,
                search_text=search_text,
                order_by=order_by,
                sort_order=sort_order
            )
        )

        if not df.empty:
            df.created = pd.to_datetime(df.created + '00', utc=True, format='%Y-%m-%d %H:%M:%S%z')

            df = df.astype(dtype={
                'name': 'string',
                'notes': 'string',
                'group_id': 'category'
            }).set_index('name')

        return df

    def tags_series(
            self,
            tag_names: List[str] = None,
            exclude_tag_names: List[str] = None,
            realtime_start: date = None,
            realtime_end: date = None,
            order_by: enums.OrderBy = enums.OrderBy.series_id,
            sort_order: enums.SortOrder = enums.SortOrder.asc
    ) -> pd.DataFrame:
        """
        ## Parameters

        `tag_names`
        Tuple of tag names that series match all of.

        `exclude_tag_names`
        Tuple of tag names that series match none of.

        `realtime_start`
        The start of the real-time period. For more information, see [Real-Time Periods](https://fred.stlouisfed.org/docs/api/fred/realtime_period.html).

        `realtime_end`
        The end of the real-time period. For more information, see [Real-Time Periods](https://fred.stlouisfed.org/docs/api/fred/realtime_period.html).

        `order_by`
        Order results by values of the specified attribute.

        `sort_order`
        Sort results is ascending or descending order for attribute values specified by order_by.

        ## Description
        https://fred.stlouisfed.org/docs/api/fred/tags_series.html

        Get the series matching all tags in the tag_names parameter and no tags in the exclude_tag_names parameter.

        ## API Request (HTTPS GET)
        https://api.stlouisfed.org/fred/tags/series?tag_names=slovenia;food;oecd&api_key=abcdefghijklmnopqrstuvwxyz123456&file_type=json

        ## API Response
        ```json
        {
          "realtime_start": "2017-08-01",
          "realtime_end": "2017-08-01",
          "order_by": "series_id",
          "sort_order": "asc",
          "count": 18,
          "offset": 0,
          "limit": 1000,
          "seriess": [
                {
                  "id": "CPGDFD02SIA657N",
                  "realtime_start": "2017-08-01",
                  "realtime_end": "2017-08-01",
                  "title": "Consumer Price Index: Total Food Excluding Restaurants for Slovenia\u00a9",
                  "observation_start": "1996-01-01",
                  "observation_end": "2016-01-01",
                  "frequency": "Annual",
                  "frequency_short": "A",
                  "units": "Growth Rate Previous Period",
                  "units_short": "Growth Rate Previous Period",
                  "seasonal_adjustment": "Not Seasonally Adjusted",
                  "seasonal_adjustment_short": "NSA",
                  "last_updated": "2017-04-20 00:48:35-05",
                  "popularity": 0,
                  "group_popularity": 0,
                  "notes": "OECD descriptor ID: CPGDFD02\\nOECD unit ID: GP\\nOECD country ID: SVN\\n\\nAll OECD data should be cited as follows: OECD, \\"Main Economic Indicators - complete database\\", Main Economic Indicators (database),http://dx.doi.org/10.1787/data-00052-en (Accessed on date)\\nCopyright, 2016, OECD. Reprinted with permission."
                },
                ...
            ]
        }
        ```

        ## Returns
        `pandas.DataFrame`

        ## Example
        ```python
        >>> fred = FRED(api_key='abcdefghijklmnopqrstuvwxyz123456')
        >>> fred.tags_series(tag_names=['food', 'oecd']).head()
                            realtime_start realtime_end                                              title observation_start observation_end  frequency frequency_short           units     units_short      seasonal_adjustment seasonal_adjustment_short              last_updated  popularity  group_popularity                                              notes
            id
            AUSCPICORAINMEI     2022-02-05   2022-02-05  Consumer Price Index: All Items Excluding Food...        1972-01-01      2020-01-01     Annual               A  Index 2015=100  Index 2015=100  Not Seasonally Adjusted                       NSA 2021-02-17 18:27:39+00:00           1                12  Copyright, 2016, OECD. Reprinted with permissi...
            AUSCPICORQINMEI     2022-02-05   2022-02-05  Consumer Price Index: All Items Excluding Food...        1971-04-01      2021-07-01  Quarterly               Q  Index 2015=100  Index 2015=100  Not Seasonally Adjusted                       NSA 2021-12-14 21:57:04+00:00          12                12  Copyright, 2016, OECD. Reprinted with permissi...
            AUSCPIFODAINMEI     2022-02-05   2022-02-05           Consumer Price Index: Food for Australia        1977-01-01      2017-01-01     Annual               A  Index 2010=100  Index 2010=100  Not Seasonally Adjusted                       NSA 2018-03-09 21:12:09+00:00           1                 2  Copyright, 2016, OECD. Reprinted with permissi...
            AUSCPIFODQINMEI     2022-02-05   2022-02-05           Consumer Price Index: Food for Australia        1976-07-01      2018-01-01  Quarterly               Q  Index 2010=100  Index 2010=100  Not Seasonally Adjusted                       NSA 2018-04-24 19:51:04+00:00           2                 2  Copyright, 2016, OECD. Reprinted with permissi...
            AUTCPICORAINMEI     2022-02-05   2022-02-05  Consumer Price Index: All Items Excluding Food...        1966-01-01      2020-01-01     Annual               A  Index 2015=100  Index 2015=100  Not Seasonally Adjusted                       NSA 2021-03-16 22:37:57+00:00           0                 1  Copyright, 2016, OECD. Reprinted with permissi...
        ```
        """

        allowed_orders = [
            enums.OrderBy.series_id,
            enums.OrderBy.title,
            enums.OrderBy.units,
            enums.OrderBy.frequency,
            enums.OrderBy.seasonal_adjustment,
            enums.OrderBy.realtime_start,
            enums.OrderBy.realtime_end,
            enums.OrderBy.last_updated,
            enums.OrderBy.observation_start,
            enums.OrderBy.observation_end,
            enums.OrderBy.popularity,
            enums.OrderBy.group_popularity,
        ]

        if order_by not in allowed_orders:
            raise ValueError('Variable order_by ({}) is not one of the values: {}'.format(order_by, ', '.join(map(str, allowed_orders))))

        if realtime_start is not None and realtime_start < date(1776, 7, 4):
            raise ValueError('Variable realtime_start ("{}") is before min date 1776-07-04.'.format(realtime_start))

        if realtime_start is not None and realtime_end is not None and realtime_start > realtime_end:
            raise ValueError('The date set by variable realtime_start ("{}") can not be after the date set by variable realtime_end ("{}").'.format(realtime_start, realtime_end))

        df = pd.DataFrame(
            self._client.get(
                '/fred/tags/series',
                'seriess',
                limit=1000,
                tag_names=tag_names,
                exclude_tag_names=exclude_tag_names,
                realtime_start=realtime_start,
                realtime_end=realtime_end,
                order_by=order_by,
                sort_order=sort_order
            )
        )

        date_columns = [
            'realtime_start', 'realtime_end',
            'observation_start', 'observation_end',
        ]

        if not df.empty:
            df[date_columns] = df[date_columns].apply(pd.to_datetime, format='%Y-%m-%d')
            df.last_updated = pd.to_datetime(df.last_updated + '00', utc=True, format='%Y-%m-%d %H:%M:%S%z')

            df = df.astype(dtype={
                'id': 'string',
                'notes': 'string',
                'title': 'string',
                'frequency': 'category',
                'frequency_short': 'category',
                'units_short': 'category',
                'units': 'category',
                'seasonal_adjustment': 'category',
                'seasonal_adjustment_short': 'category'
            }).set_index('id')

        return df


class ALFRED(FRED):
    """
    ALFRED stands for Archival Federal Reserve Economic Data.
    ALFRED archives FRED data by adding the real-time period when values were originally released and later revised. For instance on February 2, 1990, the US Bureau of Labor Statistics reported the US unemployment rate for the month of January, 1990 as 5.3 percent.
    Over 6 years later on March 8, 1996, the US unemployment rate for the same month January, 1990 was revised to 5.4 percent.

    https://alfred.stlouisfed.org/

    https://fred.stlouisfed.org/docs/api/fred/alfred.html
    """


class GeoFRED:
    """
    The GeoFRED API is a web service that allows developers to write programs and build applications to harvest data and shape files found in GeoFRED website hosted by the Economic Research Division of the Federal Reserve Bank of St. Louis.

    https://geofred.stlouisfed.org/

    https://geofred.stlouisfed.org/docs/api/geofred/
    """
    EMPTY_VALUE = '.'

    """
    https://geofred.stlouisfed.org/
    https://geofred.stlouisfed.org/docs/api/geofred/
    """

    def __init__(self, api_key: str):
        if api_key is None:
            raise Exception('Variable api_key is not set.')

        self._client = Client(api_key, ratelimiter_enabled=False, ratelimiter_max_calls=2, ratelimiter_period=1)

    @property
    def rate_limit(self) -> int:
        return self._client.rate_limit

    @property
    def rate_limit_remaining(self) -> int:
        return self._client.rate_limit_remaining

    def shapes(self, shape: enums.ShapeType) -> List[models.Shape]:
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
        """

        wkt_list = self._client.get(
            '/geofred/shapes/file',
            shape.value,
            shape=shape
        )

        # replace whitespaces in dict keys
        for wkt in wkt_list:
            for key in list(wkt.keys()):
                wkt[key.replace(' ', '_')] = wkt.pop(key)

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
        """

        data = self._client.get(
            '/geofred/series/group',
            'series_group',
            series_id=series_id
        )

        return models.SeriesGroup(**data[0])

    def series_data(self, series_id: str, date: date = None, start_date: date = None) -> pd.DataFrame:
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

        This request returns a cross section of regional data for a specified release date.
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
              "2020": [
                {
                  "region": "Alabama",
                  "code": "01",
                  "value": "46479.0",
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
               region code    value series_id  year
        0     Alabama   01  46479.0    ALPCPI  2020
        1      Alaska   02  63502.0    AKPCPI  2020
        2     Arizona   04  49648.0    AZPCPI  2020
        3    Arkansas   05  47235.0    ARPCPI  2020
        4  California   06  70192.0    CAPCPI  2020
        ```
        """

        years = self._client.get(
            '/geofred/series/data',
            'meta.data',
            series_id=series_id,
            date=date,
            start_date=start_date
        )

        df = pd.DataFrame(
            self._add_years(years[0])
        )

        if not df.empty:
            df.value = df.value.replace(self.EMPTY_VALUE, np.nan)

            df = df.astype(dtype={
                'value': 'float64',
                'year': 'int64'
            })

        return df

    def regional_data(
            self,
            series_group: str,
            region_type: enums.RegionType,
            date: date,
            season: enums.Seasonality,
            units: str = 'Dollars',  # Documentation is missing
            start_date: date = None,
            frequency: enums.Frequency = None,
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
              "2013": [
                {
                  "region": "Alabama",
                  "code": "01",
                  "value": "36258.0",
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
               region code    value series_id  year
        0     Alabama   01  36258.0    ALPCPI  2013
        1      Alaska   02  52843.0    AKPCPI  2013
        2     Arizona   04  36739.0    AZPCPI  2013
        3    Arkansas   05  36605.0    ARPCPI  2013
        4  California   06  48549.0    CAPCPI  2013
        ```
        """

        if frequency is not None and frequency not in enums.Frequency:
            raise ValueError('Variable frequency is not one of the values: {}'.format(', '.join(map(str, enums.Frequency))))

        if aggregation_method not in enums.AggregationMethod:
            raise ValueError('Variable aggregation_method is not one of the values: {}'.format(', '.join(map(str, enums.AggregationMethod))))

        if transformation not in enums.Unit:
            raise ValueError('Variable transformation is not one of the values: {}'.format(', '.join(map(str, enums.Unit))))

        years = self._client.get(
            '/geofred/regional/data',
            'meta.data',
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

            df = df.astype(dtype={
                'value': 'float64',
                'year': 'int64'
            })

        return df

    def _add_years(self, data: dict) -> Generator[dict, None, None]:
        """
        transform dict indexed by year from:
        ```json
        {
          "2020": [
            {
              "region": "Alabama",
              "code": "01",
              "value": "46479.0",
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
            "value": "46479.0",
            "series_id": "ALPCPI",
            "year": "2020"
          },
          ...
        ]
        ```
        """
        for year, rows in data.items():
            for row in rows:
                row['year'] = year
                yield row


class FRASER:
    """
    FRASER is a digital library of U.S. economic, financial, and banking history—particularly the history of the Federal Reserve System.

    Providing economic information and data to the public is an important mission for the St. Louis Fed started by former St. Louis Fed Research Director Homer Jones in 1958.
    FRASER began as a data preservation and accessibility project of the Federal Reserve Bank of St. Louis in 2004 and now provides access to data and policy documents from the Federal Reserve System and many other institutions.

    https://fraser.stlouisfed.org/
    https://research.stlouisfed.org/docs/api/fraser/
    """

    def __init__(self):
        self._sickle = sickle.Sickle('https://fraser.stlouisfed.org/oai')

    def list_records(self, ignore_deleted: bool = False, set: str = None) -> sickle.iterator.BaseOAIIterator:
        """
        ## Parameters

        `set`
        This parameter specifies the setSpec value and limits the records that are retrieved to only those in the specified set.
        Ignore this parameter to return all records.

        ## Description
        https://research.stlouisfed.org/docs/api/fraser/listRecords.html

        This request returns title records from the FRASER repository.
        A resumptionToken can be used to retrieve all records using multiple requests.

        Additional information about an individual title, including the title's child records, can be retrieved using the GetRecord request.

        ## API Request (HTTPS GET)
        https://fraser.stlouisfed.org/oai/?verb=ListRecords&metadataPrefix=mods&resumptionToken=1469299598:0

        ## Returns
        `sickle.iterator.BaseOAIIterator`

        ## Example (`pandas.DataFrame`)
        ```python
            from pystlouisfed import FRASER

            for record in FRASER().list_records():
                print(record.get_metadata())
        ```
        """

        return self._sickle.ListRecords(metadataPrefix='mods', ignore_deleted=ignore_deleted, set=set)

    def list_sets(self) -> sickle.iterator.BaseOAIIterator:
        """
        ## Description
        https://research.stlouisfed.org/docs/api/fraser/listSets.html

        This request returns the set structure for records in the FRASER repository.
        A resumptionToken can be used to retrieve the complete set structure using multiple requests.

        ## API Request (HTTPS GET)
        https://fraser.stlouisfed.org/oai/?verb=ListSets&resumptionToken=1478707638:0

        ## Returns
        `sickle.iterator.BaseOAIIterator`

        ## Example (`pandas.DataFrame`)
        ```python
            from pystlouisfed import FRASER

            for set in FRASER().list_sets():
                print(set)
        ```
        """

        return self._sickle.ListSets()

    def list_identifiers(self, ignore_deleted: bool = False, set: str = None) -> sickle.iterator.BaseOAIIterator:
        """
        ## Parameters

        `set`
        This parameter specifies the setSpec value and limits the records that are retrieved to only those in the specified set Ignore this parameter to return all records.

        ## Description
        https://research.stlouisfed.org/docs/api/fraser/listIdentifiers.html

        This request returns headers for records in the FRASER repository.
        A resumptionToken can be used to retrieve all records using multiple requests.

        ## API Request (HTTPS GET)
        https://fraser.stlouisfed.org/oai/?verb=ListIdentifiers&resumptionToken=1469300451:0

        ## Returns
        `sickle.iterator.BaseOAIIterator`

        ## Example (`pandas.DataFrame`)
        ```python
            from pystlouisfed import FRASER

            for header in FRASER().list_identifiers():
                print(header.identifier)
        ```
        """

        return self._sickle.ListIdentifiers(metadataPrefix='mods', ignore_deleted=ignore_deleted, set=set)

    def get_record(self, identifier: str) -> sickle.models.Record:
        """
        ## Description
        https://research.stlouisfed.org/docs/api/fraser/getRecord.html

        This request returns a single record from the FRASER repository.

        ## API Request (HTTPS GET)
        https://fraser.stlouisfed.org/oai/?verb=GetRecord&identifier=oai:fraser.stlouisfed.org:title:176

        ## Returns
        `sickle.models.Record`

        ## Example (`pandas.DataFrame`)
        ```python
            from pystlouisfed import FRASER

            FRASER().get_record(identifier='oai:fraser.stlouisfed.org:title:176')
        ```
        """

        return self._sickle.GetRecord(identifier=identifier, metadataPrefix='mods')
