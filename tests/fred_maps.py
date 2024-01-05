import datetime
import json
from pathlib import Path
import unittest
from unittest import mock
from urllib.parse import parse_qsl
from urllib.parse import urlparse

from pystlouisfed import Frequency
from pystlouisfed import FREDMaps
from pystlouisfed import RegionType
from pystlouisfed import Seasonality
from pystlouisfed import ShapeType


class MockRequestsResponse:
    def __init__(self, name: str):
        self.name = name
        self.status_code = 200
        self.headers = {
            "content-type": "application/json",
            "x-rate-limit-limit": 120,
            "x-rate-limit-remaining": 119
        }
        self._fixtures_path = Path(f"./fixtures/{name}.json")

    def json(self) -> dict:
        return json.loads(self._fixtures_path.read_text())


def mocked_requests_get(url, **kwargs):
    parse_result = urlparse(url)
    params_dict = {k: v for k, v in parse_qsl(parse_result.query)}

    if parse_result.path == "/geofred/series/data":
        return MockRequestsResponse("maps/series_data")
    elif parse_result.path == "/geofred/regional/data":
        return MockRequestsResponse("maps/regional_data")
    elif parse_result.path == "/geofred/shapes/file":
        return MockRequestsResponse("maps/shape")
    else:
        raise ValueError("Unexpected URL: {}".format(url))


class TestFREDMaps(unittest.TestCase):

    def setUp(self):
        self.fred_maps = FREDMaps(api_key=Path("./api.key").read_text())

    @mock.patch("requests.get", side_effect=mocked_requests_get)
    def test_series_data_fixture(self, mock_get):
        # https://api.stlouisfed.org/geofred/series/data?series_id=WIPCPI&api_key=abcdefghijklmnopqrstuvwxyz123456&file_type=json
        df = self.fred_maps.series_data(series_id="WIPCPI")

        self.assertEqual(df.shape, (51, 5))

    @mock.patch("requests.get", side_effect=mocked_requests_get)
    def test_regional_data_fixture(self, mock_get):
        # https://api.stlouisfed.org/geofred/regional/data?api_key=abcdefghijklmnopqrstuvwxyz123456&series_group=882&date=2013-01-01&region_type=state&units=&frequency=a&season=NSA&units=Dollars&file_type=json
        df = self.fred_maps.regional_data(
            series_group="882",
            date=datetime.date(2013, 1, 1),
            region_type=RegionType.state,
            frequency=Frequency.anual,
            season=Seasonality.nsa
        )

        self.assertEqual(df.shape, (51, 5))

    @mock.patch("requests.get", side_effect=mocked_requests_get)
    def test_shape(self, mock_get):
        # https://api.stlouisfed.org/geofred/shapes/file?api_key=abcdefghijklmnopqrstuvwxyz123456&file_type=json&shape=bea
        df = self.fred_maps.shapes(shape=ShapeType.state)

        self.assertEqual(df.shape, (61, 20))

    def test_series_group(self):
        series_group = self.fred_maps.series_group(series_id="SMU56000000500000001a")

        self.assertEqual(series_group.title, "All Employees: Total Private")
        self.assertEqual(series_group.region_type, "state")
        self.assertEqual(series_group.series_group, "1223")
        self.assertEqual(series_group.season, "NSA")
        self.assertEqual(series_group.units, "Thousands of Persons")
        self.assertEqual(series_group.frequency, "Annual")
        self.assertEqual(series_group.min_date, datetime.date(1990, 1, 1))
        self.assertEqual(series_group.max_date, datetime.date(2022, 1, 1))

    def test_series_data(self):
        df = self.fred_maps.series_data(series_id="WIPCPI")

        self.assertEqual(df.head().shape, (5, 5))

    def test_regional_data(self):
        df = self.fred_maps.regional_data(
            series_group="882",
            date=datetime.date(2013, 1, 1),
            region_type=RegionType.state,
            frequency=Frequency.anual,
            season=Seasonality.nsa
        )
        self.assertEqual(df.head().shape, (5, 5))


if __name__ == "__main__":
    unittest.main()
