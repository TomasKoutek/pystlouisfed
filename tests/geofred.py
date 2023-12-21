import datetime
import json
from pathlib import Path
from unittest import TestCase
from unittest import mock
from urllib.parse import parse_qsl
from urllib.parse import urlparse

from pystlouisfed import Frequency
from pystlouisfed import GeoFRED
from pystlouisfed import RegionType
from pystlouisfed import Seasonality


class MockRequestsResponse:
    def __init__(self, name: str):
        self.name = name
        self.status_code = 200
        self.headers = {
            "content-type": "application/json",
            "x-rate-limit-limit": 120,
            "x-rate-limit-remaining": 119
        }
        self._fixtures_path = Path("./fixtures")

    def json(self):
        return self._load_fixture()

    def _load_fixture(self):
        with self._fixtures_path.joinpath(self.name + ".json").open() as f:
            return json.loads(f.read())


def mocked_requests_get(url, **kwargs):
    parse_result = urlparse(url)
    params_dict = {k: v for k, v in parse_qsl(parse_result.query)}

    if parse_result.path == "/fred/category":
        return MockRequestsResponse("category")
    elif parse_result.path == "/fred/release":
        return MockRequestsResponse("release")
    elif parse_result.path == "/fred/series":
        return MockRequestsResponse("series")
    elif parse_result.path == "/geofred/series/data":
        return MockRequestsResponse("series_data")
    elif parse_result.path == "/geofred/regional/data":
        return MockRequestsResponse("regional_data")
    else:
        raise ValueError("Unexpected URL: {}".format(url))


class TestGeoFRED(TestCase):

    def setUp(self):
        with Path("./api.key").open() as f:
            api_key = f.read()

        self.geo_fred = GeoFRED(api_key=api_key)

    @mock.patch("requests.get", side_effect=mocked_requests_get)
    def test_series_data_fixture(self, mock_get):
        df = self.geo_fred.series_data(series_id="WIPCPI")

        self.assertEqual(df.shape, (51, 5))

    @mock.patch("requests.get", side_effect=mocked_requests_get)
    def test_regional_data_fixture(self, mock_get):
        df = self.geo_fred.regional_data(series_group="882", date=datetime.date(2013, 1, 1), region_type=RegionType.state, frequency=Frequency.anual, season=Seasonality.nsa)

        self.assertEqual(df.shape, (51, 5))

    def test_series_group(self):
        series_group = self.geo_fred.series_group(series_id="SMU56000000500000001a")
        self.assertEqual(series_group.title, "All Employees: Total Private")
        self.assertEqual(series_group.region_type, "state")
        self.assertEqual(series_group.series_group, "1223")
        self.assertEqual(series_group.season, "NSA")
        self.assertEqual(series_group.units, "Thousands of Persons")
        self.assertEqual(series_group.frequency, "Annual")
        self.assertEqual(series_group.min_date, datetime.date(1990, 1, 1))
        self.assertEqual(series_group.max_date, datetime.date(2022, 1, 1))

    def test_series_data(self):
        df = self.geo_fred.series_data(series_id="WIPCPI")
        self.assertEqual(df.head().shape, (5, 5))

    def test_regional_data(self):
        df = self.geo_fred.regional_data(
            series_group="882",
            date=datetime.date(2013, 1, 1),
            region_type=RegionType.state,
            frequency=Frequency.anual,
            season=Seasonality.nsa
        )
        self.assertEqual(df.head().shape, (5, 5))
