__version__ = "2.2.1"

from .alfred import FRED, ALFRED
from .geofred import GeoFRED
from .fraser import FRASER
from .enums import SortOrder, TagGroupID, FilterVariable, Seasonality, FilterValue, OrderBy, Unit, Frequency, AggregationMethod, OutputType, SearchType, RegionType, ShapeType
from .models import Release, Category, Shape, Source, Series, SeriesGroup

__all__ = [
    "FRED", "ALFRED", "GeoFRED", "FRASER",
    "SortOrder", "TagGroupID", "FilterVariable", "Seasonality", "FilterValue", "OrderBy", "Unit", "Frequency", "AggregationMethod",
    "OutputType", "SearchType", "RegionType", "ShapeType",
    "Release", "Category", "Shape", "Source", "Series", "SeriesGroup"
]

__pdoc__ = {
    "client.Client": False,
    "client.URLFactory": False,
    "models.Tag": False,
    "models.ReleaseDate": False,
    "models.Observation": False
}
