__version__ = '2.1.1'

from pystlouisfed.client import FRED, ALFRED, GeoFRED, FRASER
from pystlouisfed.enums import SortOrder, TagGroupID, FilterVariable, Seasonality, FilterValue, OrderBy, Unit, Frequency, AggregationMethod, OutputType, SearchType, RegionType, ShapeType
from pystlouisfed.models import Release, Category, Shape, Source, Series, SeriesGroup

__all__ = [
    "FRED", "ALFRED", "GeoFRED", "FRASER",
    "SortOrder", "TagGroupID", "FilterVariable", "Seasonality", "FilterValue", "OrderBy", "Unit", "Frequency", "AggregationMethod",
    "OutputType", "SearchType", "RegionType", "ShapeType",
    "Release", "Category", "Shape", "Source", "Series", "SeriesGroup"
]

__pdoc__ = {
    'client.Client': False,
    'client.URLFactory': False,
    'models.Tag': False,
    'models.ReleaseDate': False,
    'models.Observation': False
}
