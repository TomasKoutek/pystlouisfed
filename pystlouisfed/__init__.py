__version__ = "3.0.0"

from .alfred import FRED, ALFRED
from .fredmaps import FREDMaps
from .fraser import FRASER
from .enums import SortOrder, TagGroupID, FilterVariable, Seasonality, FilterValue, OrderBy, Unit, Frequency, AggregationMethod, OutputType, SearchType, RegionType, ShapeType
from .models import Release, Category, Source, Series, SeriesGroup

__all__ = [
    "FRED", "ALFRED", "FREDMaps", "FRASER",
    "SortOrder", "TagGroupID", "FilterVariable", "Seasonality", "FilterValue", "OrderBy", "Unit", "Frequency", "AggregationMethod",
    "OutputType", "SearchType", "RegionType", "ShapeType",
    "Release", "Category", "Source", "Series", "SeriesGroup"
]

__pdoc__ = {
    "client.Client": False,
    "client.URLFactory": False,
    "models.Tag": False,
    "models.ReleaseDate": False,
    "models.Observation": False
}
