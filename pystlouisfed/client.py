import logging
import time
import xml.etree.ElementTree as ET
from datetime import datetime
from datetime import timedelta
from enum import Enum
from functools import reduce
from http import HTTPStatus
from typing import ClassVar
from typing import NoReturn
from typing import Optional

import requests
from rush.limiters.periodic import PeriodicLimiter
from rush.quota import Quota
from rush.stores.dictionary import DictionaryStore
from rush.throttle import Throttle

logger = logging.getLogger(__name__)


class URLFactory:
    SEPARATOR = ";"

    def __init__(self, key: str, base: str = "https://api.stlouisfed.org") -> NoReturn:
        self._base = base
        self._params = {
            "api_key": key,
            "file_type": "json"
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
            # Example: 2018-03-02 02:20 would be 201803020220
            if isinstance(v, datetime):
                filtered[k] = v.strftime("%Y%m%d%H%M")

            # replace whitespaces with +
            if isinstance(filtered[k], str):
                filtered[k] = filtered[k].replace(" ", "+")

        payload_str = "&".join(f"{k}={v}" for k, v in {**self._params, **filtered}.items())

        url = f"{self._base}{endpoint}?{payload_str}"
        logger.debug(f"URL: {url}")

        return url


class Client:
    _headers: ClassVar[dict] = {
        "Accept": "application/json",
        "Accept-Encoding": "gzip",
        "Cache-Control": "no-cache",
        "User-Agent": "Python FRED Client"
    }
    HTTP_TOO_MANY_REQUESTS_IN_SHORT_PERIOD: ClassVar[int] = 420

    def __init__(self, key: str, ratelimiter_enabled: bool, ratelimiter_max_calls: int, ratelimiter_period: timedelta, request_params: Optional[dict] = None) -> NoReturn:
        self._url: URLFactory = URLFactory(key)
        self._ratelimiter_enabled = ratelimiter_enabled

        if ratelimiter_enabled:
            self._ratelimiter_max_calls = ratelimiter_max_calls

            self._rate_limiter = Throttle(
                limiter=PeriodicLimiter(
                    store=DictionaryStore()
                ),
                rate=Quota(
                    period=ratelimiter_period,
                    count=ratelimiter_max_calls
                )
            )

        if request_params is None:
            request_params = {}

        if "headers" not in request_params:
            request_params["headers"] = self._headers

        self.request_params = request_params

    def get(self, endpoint: str, list_key: str, limit: Optional[int] = None, **kwargs) -> list:

        offset = 0 if limit is not None else None
        stop = False
        result = []
        request_number = 1

        while not stop:

            url = self._url.create(
                endpoint, {
                    "limit": limit,
                    "offset": offset,
                    **kwargs,
                }
            )

            if self._ratelimiter_enabled:

                while True:
                    limit_result = self._rate_limiter.check("all", 1)

                    if limit_result.limited:
                        logger.debug(f"Api request limited! The limit will be reset after {limit_result.reset_after}.")
                        time.sleep(1 if not limit_result.reset_after.seconds else limit_result.reset_after.seconds)
                    else:
                        break

                logger.debug(
                    f"Api rate limit: {limit_result.remaining} out of {self._ratelimiter_max_calls} requests per minute remaining. The limit will be reset after {limit_result.reset_after}.")

            res = requests.get(url, **self.request_params)

            # GeoFRED return error codes and messages in XML
            if res.headers.get("content-type").startswith("text/xml") and res.status_code != HTTPStatus.OK.value:
                element = ET.fromstring(res.content.decode())
                raise ValueError(f'Received error code: "{element.get("code")}" and message: "{element.get("message")}" for URL {url}')

            elif not res.headers.get("content-type").startswith("application/json"):
                raise ValueError(f'Unexpected content-type "{res.headers.get("content-type")}" for URL {url}')

            data = res.json()

            if res.status_code in [
                HTTPStatus.BAD_REQUEST.value,
                HTTPStatus.FORBIDDEN.value,
                HTTPStatus.TOO_MANY_REQUESTS.value,
                self.HTTP_TOO_MANY_REQUESTS_IN_SHORT_PERIOD,
                HTTPStatus.INTERNAL_SERVER_ERROR.value,
            ]:
                raise ValueError(f'Received error code: "{data["error_code"]}" and message: "{" ".join(data["error_message"].split())}" for URL {url}')
            elif res.status_code != HTTPStatus.OK.value:
                raise ValueError(f'Received status code: "{res.status_code}" for URL {url}')

            list_data = self._deep_get(data, list_key)

            if "count" not in data:
                # GeoFRED.series_data and GeoFRED.regional_data return dict of years
                return list_data if isinstance(list_data, list) else [list_data]
            else:
                number_of_requests = int(data["count"] / limit) + 1 if limit is not None else 1
                logger.debug(f"Number of records: {data['count']}, Request {request_number} of {number_of_requests}")

            if limit is None or data["count"] < limit or len(list_data) < limit:
                stop = True

            if len(list_data) == limit:
                offset += limit

            result += list_data
            request_number += 1

        return result

    def _deep_get(self, dictionary: dict, keys: str, default=None):
        return reduce(lambda d, key: d.get(key, default) if isinstance(d, dict) else default, keys.split("."), dictionary)
