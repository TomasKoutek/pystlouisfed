import datetime
import json
from pathlib import Path
from unittest import main, mock, TestCase
from urllib.parse import urlparse, parse_qsl

from pystlouisfed import *


class MockRequestsResponse:
    def __init__(self, name: str):
        self.name = name
        self.status_code = 200
        self.headers = {
            'content-type': 'application/json',
            'x-rate-limit-limit': 120,
            'x-rate-limit-remaining': 119
        }
        self._fixtures_path = Path('./fixtures')

    def json(self):
        return self._load_fixture()

    def _load_fixture(self):
        with self._fixtures_path.joinpath(self.name + '.json').open() as f:
            return json.loads(f.read())


def mocked_requests_get(url, **kwargs):
    parse_result = urlparse(url)
    params_dict = {k: v for k, v in parse_qsl(parse_result.query)}

    if parse_result.path == '/fred/category':
        return MockRequestsResponse('category')
    elif parse_result.path == '/fred/release':
        return MockRequestsResponse('release')
    elif parse_result.path == '/fred/series':
        return MockRequestsResponse('series')
    elif parse_result.path == '/geofred/series/data':
        return MockRequestsResponse('series_data')
    elif parse_result.path == '/geofred/regional/data':
        return MockRequestsResponse('regional_data')
    else:
        raise ValueError('Unexpected URL: {}'.format(url))


class TestFRED(TestCase):

    def setUp(self):
        with Path('./api.key').open() as f:
            api_key = f.read()

        self.fred = FRED(api_key=api_key)

    @mock.patch('requests.get', side_effect=mocked_requests_get)
    def test_category_fixture(self, mock_get):
        category = self.fred.category(category_id=125)

        self.assertEqual(category.id, 125)
        self.assertEqual(category.name, 'Trade Balance')
        self.assertEqual(category.parent_id, 13)

    @mock.patch('requests.get', side_effect=mocked_requests_get)
    def test_release_fixture(self, mock_get):
        release = self.fred.release(release_id=53, realtime_start=datetime.date(2023, 7, 20), realtime_end=datetime.date(2023, 7, 21))
        self.assertEqual(release.id, 53)
        self.assertEqual(release.realtime_start, datetime.date(2023, 7, 20))
        self.assertEqual(release.realtime_end, datetime.date(2023, 7, 21))
        self.assertEqual(release.name, 'Gross Domestic Product')
        self.assertEqual(release.press_release, True)
        self.assertEqual(release.link, 'https://www.bea.gov/data/gdp/gross-domestic-product')

    @mock.patch('requests.get', side_effect=mocked_requests_get)
    def test_series_fixture(self, mock_get):
        series = self.fred.series(series_id='GNPCA', realtime_start=datetime.date(2023, 7, 20), realtime_end=datetime.date(2023, 7, 21))

        self.assertEqual(series.id, 'GNPCA')
        self.assertEqual(series.realtime_start, datetime.date(2023, 7, 20))
        self.assertEqual(series.realtime_end, datetime.date(2023, 7, 21))
        self.assertEqual(series.title, 'Real Gross National Product')
        self.assertEqual(series.observation_start, datetime.date(1929, 1, 1))
        self.assertEqual(series.observation_end, datetime.date(2022, 1, 1))
        self.assertEqual(series.frequency, 'Annual')
        self.assertEqual(series.frequency_short, 'A')
        self.assertEqual(series.units, 'Billions of Chained 2012 Dollars')
        self.assertEqual(series.units_short, 'Bil. of Chn. 2012 $')
        self.assertEqual(series.seasonal_adjustment, 'Not Seasonally Adjusted')
        self.assertEqual(series.seasonal_adjustment_short, 'NSA')
        self.assertEqual(series.last_updated, datetime.datetime(2023, 3, 30, 7, 54, 21, tzinfo=datetime.timezone(datetime.timedelta(days=-1, seconds=68400))))
        self.assertEqual(series.popularity, 13)
        self.assertEqual(series.notes, 'BEA Account Code: A001RX\n\n')

    def test_category(self):
        category = self.fred.category(category_id=125)
        self.assertEqual(category.id, 125)
        self.assertEqual(category.name, 'Trade Balance')
        self.assertEqual(category.parent_id, 13)

    def test_category_children(self):
        df = self.fred.category_children(category_id=13)
        self.assertEqual(df.head().shape, (5, 2))

    def test_category_related(self):
        df = self.fred.category_related(category_id=32073)
        self.assertEqual(df.head().shape, (5, 2))

    def test_category_series(self):
        df = self.fred.category_series(category_id=125)
        self.assertEqual(df.head().shape, (5, 15))

    def test_category_tags(self):
        df = self.fred.category_tags(category_id=125)
        self.assertEqual(df.head().shape, (5, 5))

    def test_category_related_tags(self):
        df = self.fred.category_related_tags(category_id=125, tag_names=['services', 'quarterly'])
        self.assertEqual(df.head().shape, (5, 5))

    def test_releases(self):
        df = self.fred.releases()
        self.assertEqual(df.head().shape, (5, 6))

    def test_releases_dates(self):
        df = self.fred.releases_dates(realtime_start=datetime.date.today() - datetime.timedelta(days=1))
        self.assertEqual(df.head().shape, (5, 2))

    def test_release(self):
        release = self.fred.release(release_id=53, realtime_start=datetime.date(2023, 7, 20), realtime_end=datetime.date(2023, 7, 21))
        self.assertEqual(release.id, 53)
        self.assertEqual(release.realtime_start, datetime.date(2023, 7, 20))
        self.assertEqual(release.realtime_end, datetime.date(2023, 7, 21))
        self.assertEqual(release.name, 'Gross Domestic Product')
        self.assertEqual(release.press_release, True)
        self.assertEqual(release.link, 'https://www.bea.gov/data/gdp/gross-domestic-product')

    def test_release_dates(self):
        df = self.fred.release_dates(release_id=82)
        self.assertEqual(df.head().shape, (5, 2))

    def test_release_series(self):
        df = self.fred.release_series(release_id=51)
        self.assertEqual(df.head().shape, (5, 15))

    def test_release_sources(self):
        df = self.fred.release_sources(release_id=51)
        self.assertEqual(df.head().shape, (2, 4))

    def test_release_tags(self):
        df = self.fred.release_tags(release_id=86)
        self.assertEqual(df.head().shape, (5, 5))

    def test_release_related_tags(self):
        df = self.fred.release_related_tags(release_id=86, tag_names=['sa', 'foreign'])
        self.assertEqual(df.head().shape, (5, 5))

    def test_series(self):
        series = self.fred.series(series_id='GNPCA', realtime_start=datetime.date(2023, 7, 20), realtime_end=datetime.date(2023, 7, 21))
        self.assertEqual(series.id, 'GNPCA')
        self.assertEqual(series.realtime_start, datetime.date(2023, 7, 20))
        self.assertEqual(series.realtime_end, datetime.date(2023, 7, 21))
        self.assertEqual(series.title, 'Real Gross National Product')
        self.assertEqual(series.observation_start, datetime.date(1929, 1, 1))
        self.assertEqual(series.observation_end, datetime.date(2022, 1, 1))
        self.assertEqual(series.frequency, 'Annual')
        self.assertEqual(series.frequency_short, 'A')
        self.assertEqual(series.units, 'Billions of Chained 2012 Dollars')
        self.assertEqual(series.units_short, 'Bil. of Chn. 2012 $')
        self.assertEqual(series.seasonal_adjustment, 'Not Seasonally Adjusted')
        self.assertEqual(series.seasonal_adjustment_short, 'NSA')
        self.assertEqual(series.last_updated, datetime.datetime(2023, 3, 30, 7, 54, 21, tzinfo=datetime.timezone(datetime.timedelta(days=-1, seconds=68400))))
        self.assertEqual(series.popularity, 13)
        self.assertEqual(series.notes, 'BEA Account Code: A001RX\n\n')

    def test_series_categories(self):
        df = self.fred.series_categories(series_id='EXJPUS')
        self.assertEqual(df.head().shape, (2, 2))

    def test_series_observations_realtime_period(self):
        df = self.fred.series_observations(
            series_id='GNPCA',
            output_type=OutputType.realtime_period,
            realtime_start=datetime.date(2020, 7, 4),
            realtime_end=datetime.date(2023, 7, 20),
            observation_start=datetime.date(1990, 7, 1),
            observation_end=datetime.date(2023, 7, 1)
        )
        self.assertEqual(df.head().shape, (5, 3))

    def test_series_observations_all(self):
        df = self.fred.series_observations(
            series_id='GNPCA',
            output_type=OutputType.all,
            realtime_start=datetime.date(2020, 7, 4),
            realtime_end=datetime.date(2023, 7, 20),
            observation_start=datetime.date(1990, 7, 1),
            observation_end=datetime.date(2023, 7, 1)
        )
        self.assertEqual(df.head().shape, (5, 8))

    def test_series_observations_new_and_revised(self):
        df = self.fred.series_observations(
            series_id='GNPCA',
            output_type=OutputType.new_and_revised,
            realtime_start=datetime.date(2020, 7, 4),
            realtime_end=datetime.date(2023, 7, 20),
            observation_start=datetime.date(1990, 7, 1),
            observation_end=datetime.date(2023, 7, 1)
        )
        self.assertEqual(df.head().shape, (5, 6))

    def test_series_observations_initial_release_only(self):
        df = self.fred.series_observations(
            series_id='GNPCA',
            output_type=OutputType.initial_release_only,
            realtime_start=datetime.date(2020, 7, 4),
            realtime_end=datetime.date(2023, 7, 20),
            observation_start=datetime.date(1990, 7, 1),
            observation_end=datetime.date(2023, 7, 1)
        )
        self.assertEqual(df.head().shape, (3, 3))

    def test_series_release(self):
        df = self.fred.series_release(series_id='IRA')
        self.assertEqual(df.head().shape, (1, 5))

    def test_series_search(self):
        df = self.fred.series_search(search_text='monetary service index')
        self.assertEqual(df.head().shape, (5, 15))

    def test_series_search_tags(self):
        df = self.fred.series_search_tags(series_search_text='monetary service index')
        self.assertEqual(df.head().shape, (5, 5))

    def test_series_search_related_tags(self):
        df = self.fred.series_search_related_tags(
            series_search_text='mortgage rate',
            tag_names=['30-year', 'frb'],
            realtime_start=datetime.date(2022, 1, 5),
            realtime_end=datetime.date(2022, 1, 5)
        )
        self.assertEqual(df.head().shape, (5, 5))

    def test_series_tags(self):
        df = self.fred.series_tags(series_id='STLFSI')
        self.assertEqual(df.head().shape, (5, 5))

    def test_series_updates(self):
        df = self.fred.series_updates(
            start_time=datetime.datetime.today() - datetime.timedelta(days=2),
            end_time=datetime.datetime.today() - datetime.timedelta(days=1)
        )
        self.assertEqual(df.head().shape, (5, 14))

    def test_series_vintagedates(self):
        df = self.fred.series_vintagedates(series_id='GNPCA')
        self.assertEqual(df.head().shape, (5,))

    def test_sources(self):
        df = self.fred.sources()
        self.assertEqual(df.head().shape, (5, 5))

    def test_source(self):
        source = self.fred.source(source_id=1, realtime_start=datetime.date(2023, 7, 27), realtime_end=datetime.date(2023, 7, 27))
        self.assertEqual(source.id, 1)
        self.assertEqual(source.realtime_start, datetime.date(2023, 7, 27))
        self.assertEqual(source.realtime_end, datetime.date(2023, 7, 27))
        self.assertEqual(source.name, 'Board of Governors of the Federal Reserve System (US)')
        self.assertEqual(source.link, 'http://www.federalreserve.gov/')

    def test_source_releases(self):
        df = self.fred.source_releases(source_id=1)
        self.assertEqual(df.head().shape, (5, 6))

    def test_tags(self):
        df = self.fred.tags()
        self.assertEqual(df.head().shape, (5, 5))

    def test_related_tags(self):
        df = self.fred.related_tags(tag_names=['monetary aggregates', 'weekly'])
        self.assertEqual(df.head().shape, (5, 5))

    def test_tags_series(self):
        df = self.fred.tags_series(tag_names=['food', 'oecd'])
        self.assertEqual(df.head().shape, (5, 15))


class TestGeoFRED(TestCase):

    def setUp(self):
        with Path('./api.key').open() as f:
            api_key = f.read()

        self.geo_fred = GeoFRED(api_key=api_key)

    @mock.patch('requests.get', side_effect=mocked_requests_get)
    def test_series_data_fixture(self, mock_get):
        df = self.geo_fred.series_data(series_id="WIPCPI")

        self.assertEqual(df.shape, (51, 5))

    @mock.patch('requests.get', side_effect=mocked_requests_get)
    def test_regional_data_fixture(self, mock_get):
        df = self.geo_fred.regional_data(series_group='882', date=datetime.date(2013, 1, 1), region_type=RegionType.state, frequency=Frequency.anual, season=Seasonality.nsa)

        self.assertEqual(df.shape, (51, 5))

    def test_series_group(self):
        series_group = self.geo_fred.series_group(series_id='SMU56000000500000001a')
        self.assertEqual(series_group.title, 'All Employees: Total Private')
        self.assertEqual(series_group.region_type, 'state')
        self.assertEqual(series_group.series_group, '1223')
        self.assertEqual(series_group.season, 'NSA')
        self.assertEqual(series_group.units, 'Thousands of Persons')
        self.assertEqual(series_group.frequency, 'Annual')
        self.assertEqual(series_group.min_date, datetime.date(1990, 1, 1))
        self.assertEqual(series_group.max_date, datetime.date(2022, 1, 1))

    def test_series_data(self):
        df = self.geo_fred.series_data(series_id="WIPCPI")
        self.assertEqual(df.head().shape, (5, 5))

    def test_regional_data(self):
        df = self.geo_fred.regional_data(
            series_group='882',
            date=datetime.date(2013, 1, 1),
            region_type=RegionType.state,
            frequency=Frequency.anual,
            season=Seasonality.nsa
        )
        self.assertEqual(df.head().shape, (5, 5))


if __name__ == '__main__':
    main()
