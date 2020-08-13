import os
import pandas as pd

from preprocessing import parse_html_to_df

# Either read and save new data or load available data
# Returns Dict{"mapsets": pd.DataFrame, "mappers": pd.DataFrame, "nominators": pd.DataFrame}
def get_data(rebuild: bool = False) -> dict:
    if rebuild:
        dfs = parse_html_to_df(
            "Aiess Project - rankfeed - rankfeed_osu [447831906655010828] 13082020.html"
        )
        for k, v in dfs.items():
            print(v)
            v.to_csv("{}.csv".format(k), index=False)
        return dfs
    else:
        return {
            "mapsets": pd.read_csv("mapsets.csv"),
            "mappers": pd.read_csv("mappers.csv"),
            "nominators": pd.read_csv("nominators.csv"),
        }


# Counts ranked maps per given period (must be in pandas.tseries.offsets)
# Returns new pd.DataFrame["date": datetime, "nr_maps": int]
def maps_per_period(mapsets: pd.DataFrame = None, period: str = "M") -> pd.DataFrame:
    mapsets = mapsets.copy()
    mapsets["date"] = pd.to_datetime(mapsets["date"])
    mapsets["date"] = mapsets["date"].dt.to_period(period).dt.to_timestamp()
    mapsets = mapsets.groupby(["date"])["set_id"].count().reset_index()
    return mapsets.rename(columns={"set_id": "nr_maps"})


# Counts ranked maps per mapper in descending order
# proportional: When True, returns ranked_by_mapper / total, otherwise returns absolute value
# Returns new pd.DataFrame["host_id": int, "nr_ranked": int, "usernames": str]
def ranked_per_mapper(
    mappers: pd.DataFrame = None,
    mapsets: pd.DataFrame = None,
    proportional: bool = False,
    ascending: bool = False,
) -> pd.DataFrame:
    mappers = mappers.copy()
    mapsets = mapsets.copy()
    df = (
        mapsets.groupby(["host_id"])["set_id"]
        .count()
        .reset_index()
        .sort_values(by="set_id", ascending=ascending)
    )
    df.rename(columns={"set_id": "nr_ranked"}, inplace=True)
    mappers.rename(columns={"user_id": "host_id"}, inplace=True)
    mappers = pd.merge(left=df, right=mappers, on="host_id")
    if proportional:
        total_mapsets = mappers["nr_ranked"].sum()
        mappers["nr_ranked"] = mappers["nr_ranked"].apply(lambda x: x / total_mapsets)
    return mappers


# Counts active nominators per given period (must be in pandas.tseries.offsets)
# Returns new pd.DataFrame["host_id": int, "nr_ranked": int, "usernames": str]
def nominators_per_period(
    nominators: pd.DataFrame = None, mapsets: pd.DataFrame = None, period: str = "M"
) -> pd.DataFrame:
    nominators = nominators.copy()
    mapsets = mapsets.copy()
    mapsets["date"] = pd.to_datetime(mapsets["date"])
    mapsets["date"] = mapsets["date"].dt.to_period(period).dt.to_timestamp()
    intervals = mapsets["date"].unique()
    dates, bns = [], []
    for interval in intervals:
        df = mapsets.loc[mapsets["date"] == interval]
        all_nominators = df[["first_nominator", "second_nominator",]].values.ravel()
        unique_values = pd.unique(all_nominators)
        dates.append(df["date"].iloc[0])
        bns.append(len(unique_values))
    return pd.DataFrame({"dates": dates, "active_nominators": bns})


# Counts maps ranked per day of the week. Generally this is the same day as when they were qualified.
# proportional: When True, returns day / total, otherwise returns absolute value
# Returns new pd.DataFrame["date": str, "nr_maps": int]
def maps_per_weekday(
    mapsets: pd.DataFrame = None, proportional: bool = True
) -> pd.DataFrame:
    mapsets = mapsets.copy()
    mapsets["date"] = pd.to_datetime(mapsets["date"])
    mapsets["date"] = mapsets["date"].dt.dayofweek
    mapsets = mapsets.groupby(["date"])["set_id"].count().reset_index()
    weekdays = [
        "Monday",
        "Tuesday",
        "Wednesday",
        "Thursday",
        "Friday",
        "Saturday",
        "Sunday",
    ]
    mapsets["date"] = mapsets["date"].apply(lambda x: weekdays[x])
    mapsets = mapsets.rename(columns={"set_id": "nr_maps"})
    if proportional:
        total_mapsets = mapsets["nr_maps"].sum()
        mapsets["nr_maps"] = mapsets["nr_maps"].apply(lambda x: x / total_mapsets)
    return mapsets


# Counts maps of other BNs nominated per BN
# Host was BN at any point in time, not necessarily when the map was ranked! All values are very inflated
# proportional: When True, returns bnmaps / total, otherwise returns absolute value
# Returns new pd.DataFrame["user_id": int, "usernames": str, "bn_maps_nominated": float]
def nominating_bn_maps(
    mapsets: pd.DataFrame = None,
    nominators: pd.DataFrame = None,
    proportional: bool = True,
    ascending: bool = False,
) -> pd.DataFrame:
    nominators = filter_by_noms(mapsets, nominators, threshold=0, minimum=True)
    mapsets = mapsets.copy()
    criterion = mapsets["host_id"].isin(nominators["user_id"])
    bn_mapsets = mapsets[criterion]
    if proportional:
        nominators["bn_maps_nominated"] = nominators["user_id"].map(
            (
                bn_mapsets["first_nominator"].value_counts()
                + bn_mapsets["second_nominator"].value_counts()
            )
            / (
                mapsets["first_nominator"].value_counts()
                + mapsets["second_nominator"].value_counts()
            )
        )
    else:
        nominators["bn_maps_nominated"] = nominators["user_id"].map(
            bn_mapsets["first_nominator"].value_counts()
            + bn_mapsets["second_nominator"].value_counts()
        )
    return nominators.sort_values(by="bn_maps_nominated", ascending=ascending).dropna()


# Nominations (only counts now ranked maps) per BN
# proportional: When True, returns noms / total, otherwise returns absolute value
# Returns new pd.DataFrame("user_id": int, "usernames": str, "nominations": float)
def nominations_per_bn(
    mapsets: pd.DataFrame = None,
    nominators: pd.DataFrame = None,
    proportional: bool = False,
    ascending: bool = False,
) -> pd.DataFrame:
    nominators = filter_by_noms(mapsets, nominators, threshold=0, minimum=True)
    mapsets = mapsets.copy()
    nominators["nominations"] = nominators["user_id"].map(
        mapsets["first_nominator"].value_counts()
        + mapsets["second_nominator"].value_counts()
    )
    if proportional:
        total_noms = (
            len(pd.unique(mapsets["set_id"])) * 2
        )  # 2 nominations per ranked map
        nominators["nominations"] = nominators["nominations"].apply(
            lambda x: x / total_noms
        )
    return nominators.sort_values(by="nominations", ascending=ascending).dropna()


# Counts activities (bubble, qf, reset, dq) max. once each per set!
# proportional: When True, returns activity / total, otherwise returns absolute value
# Returns new pd.Series
def activity_types(
    mapsets: pd.DataFrame = None, proportional: bool = False
) -> pd.Series:
    mapsets = mapsets.copy()[
        ["first_nominator", "second_nominator", "nomination_reset", "disqualification"]
    ]
    mapsets = mapsets.count()
    if proportional:
        total_activity = mapsets.sum()
        mapsets = mapsets.apply(lambda x: x / total_activity)
    return mapsets


# Counts unique mappers nominated by a BN (BNs < 10 noms omitted)
# proportional: When True, returns unique_mappers / total_noms, otherwise returns absolute value
# Returns new pd.DataFrame["user_id": int, "usernames": str, "unique_mappers": float]
def unique_mappers_nominated(
    mapsets: pd.DataFrame = None,
    nominators: pd.DataFrame = None,
    proportional: bool = True,
    ascending: bool = False,
    minimum_noms: int = 10,
) -> pd.DataFrame:
    nominators = filter_by_noms(
        mapsets, nominators, threshold=minimum_noms, minimum=True
    )
    mapsets = mapsets.copy()
    mapsets = (
        mapsets.drop(
            columns=["date", "artist", "title", "nomination_reset", "disqualification"]
        )
        .melt(id_vars=["host_id", "set_id"])
        .drop(columns=["variable"])
    )
    nominators["unique_mappers"] = nominators["user_id"].apply(
        lambda x: len(pd.unique(mapsets[mapsets["value"] == x]["host_id"]))
    )
    if proportional:
        nominators["unique_mappers"] = nominators["user_id"].apply(
            lambda x: len(pd.unique(mapsets[mapsets["value"] == x]["host_id"]))
            / mapsets[mapsets["value"] == x]["host_id"].count()
        )
    return (
        nominators.sort_values(by="unique_mappers", ascending=ascending)
        .loc[nominators["unique_mappers"] != 0]
        .dropna()
    )


# Filters list of nominators by number of nominations
# Returns new pd.DataFrame
def filter_by_noms(
    mapsets: pd.DataFrame = None,
    nominators: pd.DataFrame = None,
    threshold: int = 1,
    minimum: bool = True,
) -> pd.DataFrame:
    mapsets = mapsets.copy()
    nominators = nominators.copy()
    nominators["nominations"] = nominators["user_id"].map(
        mapsets["first_nominator"].value_counts()
        + mapsets["second_nominator"].value_counts()
    )
    if minimum:
        nominators = nominators.loc[nominators["nominations"] > threshold]
    else:
        nominators = nominators.loc[nominators["nominations"] < threshold]
    return nominators.drop(columns="nominations")

