from enum import Enum


class SortOrder(Enum):
    desc = "desc"
    """
    Descending
    """
    asc = "asc"
    """
    Ascending 
    """


class TagGroupID(Enum):
    """
    A tag group id to filter tags by type.
    """

    freq = "freq"
    """
    Frequency (same as `pystlouisfed.enums.TagGroupID.frequency`)
    """
    frequency = "freq"
    """
    Frequency (same as `pystlouisfed.enums.TagGroupID.freq`)
    """
    gen = "gen"
    """
    General or Concept (same as `pystlouisfed.enums.TagGroupID.general_or_concept`)
    """
    general_or_concept = "gen"
    """
    General or Concept (same as `pystlouisfed.enums.TagGroupID.gen`)
    """
    geo = "geo"
    """
    Geography (same as `pystlouisfed.enums.TagGroupID.geography`)
    """
    geography = "geo"
    """
    Geography (same as `pystlouisfed.enums.TagGroupID.geo`)
    """
    geot = "geot"
    """
    Geography Type (same as `pystlouisfed.enums.TagGroupID.geography_type`)
    """
    geography_type = "geot"
    """
    Geography Type (same as `pystlouisfed.enums.TagGroupID.geot`)
    """
    rls = "rls"
    """
    Release (same as `pystlouisfed.enums.TagGroupID.release`)
    """
    release = "rls"
    """
    Release (same as `pystlouisfed.enums.TagGroupID.rls`)
    """
    seas = "seas"
    """
    Seasonal Adjustment (same as `pystlouisfed.enums.TagGroupID.seasonal_adjustment`)
    """
    seasonal_adjustment = "seas"
    """
    Seasonal Adjustment (same as `pystlouisfed.enums.TagGroupID.seas`)
    """
    src = "src"
    """
    Source (same as `pystlouisfed.enums.TagGroupID.source`)
    """
    source = "src"
    """
    Source (same as `pystlouisfed.enums.TagGroupID.src`)
    """
    cc = "cc"
    """
    Citation & Copyright (same as `pystlouisfed.enums.TagGroupID.citation_and_copyright`)
    """
    citation_and_copyright = "cc"
    """
    Citation & Copyright (same as `pystlouisfed.enums.TagGroupID.cc`)
    """


class FilterVariable(Enum):
    """
    The attribute to filter results by.
    """
    frequency = "frequency"
    units = "units"
    seasonal_adjustment = "seasonal_adjustment"


class Seasonality(Enum):
    """
    The seasonality of the series group.
    """

    sa = "SA"
    """
    Seasonally Adjusted (same as `pystlouisfed.enums.Seasonality.seasonally_adjusted`)
    """
    seasonally_adjusted = "SA"
    """
    Seasonally Adjusted (same as `pystlouisfed.enums.Seasonality.sa`)
    """
    nsa = "NSA"
    """
    Not Seasonally Adjusted (same as `pystlouisfed.enums.Seasonality.not_seasonally_adjusted`)
    """
    not_seasonally_adjusted = "NSA"
    """
    Not Seasonally Adjusted (same as `pystlouisfed.enums.Seasonality.nsa`)
    """
    ssa = "SSA"
    """
    Smoothed Seasonally Adjusted (same as `pystlouisfed.enums.Seasonality.smoothed_seasonally_adjusted`)
    """
    smoothed_seasonally_adjusted = "SSA"
    """
    Smoothed Seasonally Adjusted (same as `pystlouisfed.enums.Seasonality.ssa`)
    """


class FilterValue(Enum):
    """
    The value of the filter_variable attribute to filter results by.
    """
    macro = "macro"
    """
    Limits results to macroeconomic data series. 
    In general, these are series for entire countries that are not subregions of the United States. 
    """
    regional = "regional"
    """
    Limits results to series for parts of the US; namely, series for US states, counties, and Metropolitan Statistical Areas (MSA).
    """
    all = "all"
    """
    All results.
    """


class OrderBy(Enum):
    """
    Order results by values of the specified attribute.
    """
    series_id = "series_id"
    series_count = "series_count"
    title = "title"
    units = "units"
    frequency = "frequency"
    seasonal_adjustment = "seasonal_adjustment"
    realtime_start = "realtime_start"
    realtime_end = "realtime_end"
    last_updated = "last_updated"
    observation_start = "observation_start"
    observation_end = "observation_end"
    popularity = "popularity"
    group_popularity = "group_popularity"
    created = "created"
    name = "name"
    group_id = "group_id"
    search_rank = "search_rank"
    release_id = "release_id"
    source_id = "source_id"
    press_release = "press_release"
    release_date = "release_date"
    release_name = "release_name"


class Unit(Enum):
    """
    A key that indicates a data value transformation.
    """

    lin = "lin"
    """
    Levels (No transformation)
    """
    chg = "chg"
    """
    Change
    """
    ch1 = "ch1"
    """
    Change from Year Ago
    """
    pch = "pch"
    """
    Percent Change
    """
    pc1 = "pc1"
    """
    Percent Change from Year Ago
    """
    pca = "pca"
    """
    Compounded Annual Rate of Change
    """
    cch = "cch"
    """
    Continuously Compounded Rate of Change
    """
    cca = "cca"
    """
    Continuously Compounded Annual Rate of Change
    """
    log = "log"
    """
    Natural Log
    """


class Frequency(Enum):
    """
    Parameter that indicates a lower frequency to aggregate values to.
    The FRED frequency aggregation feature converts higher frequency data series into lower frequency data series (e.g. converts a monthly data series into an annual data series).
    In FRED, the highest frequency data is daily, and the lowest frequency data is annual.
    There are 3 aggregation methods available - See `AggregationMethod`.
    """

    """
    ## Frequencies without period descriptions:
    """
    daily = "d"
    """
    Daily
    """
    weekly = "w"
    """
    Weekly
    """
    biweekly = "bw"
    """
    Biweekly
    """
    monthly = "m"
    """
    Monthly
    """
    querterly = "q"
    """
    Quarterly
    """
    semiannual = "sa"
    """
    Semiannual
    """
    anual = "a"
    """
    Annual
    """

    """
    ## Frequencies with period descriptions
    """
    wef = "wef"
    """
    Weekly Ending Friday (same as `pystlouisfed.enums.Frequency.weekly_ending_friday`)
    """
    weekly_ending_friday = "wef"
    """
    Weekly Ending Friday (same as `pystlouisfed.enums.Frequency.wef`)
    """
    weth = "weth"
    """
    Weekly Ending Thursday (same as `pystlouisfed.enums.Frequency.weekly_ending_thursday`)
    """
    weekly_ending_thursday = "weth"
    """
    Weekly Ending Thursday (same as `pystlouisfed.enums.Frequency.weth`)
    """
    wew = "wew"
    """
    Weekly Ending Wednesday (same as `pystlouisfed.enums.Frequency.weekly_ending_wednesday`)
    """
    weekly_ending_wednesday = "wew"
    """
    Weekly Ending Wednesday (same as `pystlouisfed.enums.Frequency.wew`)
    """
    wetu = "wetu"
    """
    Weekly Ending Tuesday (same as `pystlouisfed.enums.Frequency.weekly_ending_tuesday`)
    """
    weekly_ending_tuesday = "wetu"
    """
    Weekly Ending Tuesday (same as `pystlouisfed.enums.Frequency.wetu`)
    """
    wem = "wem"
    """
    Weekly Ending Monday (same as `pystlouisfed.enums.Frequency.weekly_ending_monday`)
    """
    weekly_ending_monday = "wem"
    """
    Weekly Ending Monday (same as `pystlouisfed.enums.Frequency.wem`)
    """
    wesu = "wesu"
    """
    Weekly Ending Sunday (same as `pystlouisfed.enums.Frequency.weekly_ending_sunday`)
    """
    weekly_ending_sunday = "wesu"
    """
    Weekly Ending Sunday (same as `pystlouisfed.enums.Frequency.wesu`)
    """
    wesa = "wesa"
    """
    Weekly Ending Saturday (same as `pystlouisfed.enums.Frequency.weekly_ending_saturday`)
    """
    weekly_ending_saturday = "wesa"
    """
    Weekly Ending Saturday (same as `pystlouisfed.enums.Frequency.wesa`)
    """
    bwew = "bwew"
    """
    Biweekly Ending Wednesday (same as `pystlouisfed.enums.Frequency.biweekly_ending_wednesday`)
    """
    biweekly_ending_wednesday = "bwew"
    """
    Biweekly Ending Wednesday (same as `pystlouisfed.enums.Frequency.bwew`)
    """
    bwem = "bwem"
    """
    Biweekly Ending Monday (same as `pystlouisfed.enums.Frequency.biweekly_ending_monday`)
    """
    biweekly_ending_monday = "bwem"
    """
    Biweekly Ending Monday (same as `pystlouisfed.enums.Frequency.bwem`)
    """


class AggregationMethod(Enum):
    """
    A key that indicates the aggregation method used for frequency aggregation.
    """

    avg = "avg"
    """
    Average (same as `pystlouisfed.enums.AggregationMethod.average`)
    """
    average = "avg"
    """
    Average (same as `pystlouisfed.enums.AggregationMethod.avg`)
    """
    sum = "sum"
    """
    Sum
    """
    eop = "eop"
    """
    End of Period (same as `pystlouisfed.enums.AggregationMethod.end_of_period`)
    """
    end_of_period = "eop"
    """
    End of Period (same as `pystlouisfed.enums.AggregationMethod.eop`)
    """


class OutputType(Enum):
    """
    Output type.
    """

    realtime_period = 1
    """
    Observations by Real-Time Period
    """
    all = 2
    """
    Observations by Vintage Date - All Observations
    """
    new_and_revised = 3
    """
    Observations by Vintage Date - New and Revised Observations Only
    """
    initial_release_only = 4
    """
    Observations - Initial Release Only
    """


class SearchType(Enum):
    """
    Determines the type of search to perform.
    """

    full_text = "full_text"
    """
    "full_text" searches series attributes title, units, frequency, and tags by parsing words into stems. 
    This makes it possible for searches like "Industry" to match series containing related words such as "Industries". 
    Of course, you can search for multiple words like "money" and "stock".
    """
    series_id = "series_id"
    """
    "series_id" performs a substring search on series IDs. 
    Searching for "ex" will find series containing "ex" anywhere in a series ID. 
    "*" can be used to anchor searches and match 0 or more of any character. 
    Searching for "ex*" will find series containing "ex" at the beginning of a series ID. 
    Searching for "*ex" will find series containing "ex" at the end of a series ID. 
    It"s also possible to put an "*" in the middle of a string. 
    "m*sl" finds any series starting with "m" and ending with "sl".
    """


class RegionType(Enum):
    """
    The region you want want to pull data for.
    """

    bea = "bea"
    """
    Bureau of Economic Anaylis Region
    """
    msa = "msa"
    """
    Metropolitan Statistical Area
    """
    frb = "frb"
    """
    Federal Reserve Bank Districts
    """
    necta = "necta"
    """
    New England City and Town Area
    """
    state = "state"
    """
    State
    """
    country = "country"
    """
    Country
    """
    county = "county"
    """
    USA Counties
    """
    censusregion = "censusregion"
    """
    US Census Regions
    """
    censusdivision = "censusdivision"
    """
    US Census Divisons 
    """


class ShapeType(Enum):
    """
    The type of shape you want to pull Well-known text (WKT) data for.
    """

    bea = "bea"
    """
    Bureau of Economic Anaylis Region
    """
    msa = "msa"
    """
    Metropolitan Statistical Area
    """
    frb = "frb"
    """
    Federal Reserve Bank Districts
    """
    necta = "necta"
    """
    New England City and Town Area
    """
    state = "state"
    """
    State
    """
    country = "country"
    """
    Country
    """
    county = "county"
    """
    USA Counties
    """
    censusregion = "censusregion"
    """
    US Census Regions
    """
    censusdivision = "censusdivision"
    """
    US Census Divisons 
    """
