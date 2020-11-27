import pandas as pd
from cognite.client import CogniteClient

# Few constants:
SHOW_RAW_DPS_DEFAULT = 90  # minutes
RAW_DPS_GRAN = "Raw datapoints"

# Granularity restrictions from CDF
MAX_SEC, MAX_MIN, MAX_HOUR = 120, 120, 48


def get_client(*, reload_client=False, _cache=[]):
    """Do not use this function for anything but local testing..."""
    if _CACHE_ID != id(_cache):
        raise TypeError("Do not pass kwarg '_cache'! 🤦‍♂️")
    if reload_client:
        _cache.clear()
    if _cache:
        return _cache[0]
    _cache.append(CogniteClient())  # Assumes env.vars. are set
    return _cache[0]


_CACHE_ID = id(get_client.__kwdefaults__["_cache"])


def compute_granularity(start, end, show_raw_dps, n_points):
    """
    Computes granularity based on how large the time window is currently being displayed.
    Returns two strings: CDF understandable- and "human understandable" granularity.
    """
    dur = pd.Timedelta(end - start, unit="ms")
    if dur < pd.Timedelta(show_raw_dps, "min"):
        return RAW_DPS_GRAN, RAW_DPS_GRAN

    res = dur / pd.Timedelta(1, unit="s") / n_points

    if res < MAX_SEC:
        res = round(res) or 1  # if we get 0 -> 1
        return f"{res}s", f"{res} sec{plural_suffix(res)}"

    # To avoid loosing precision with multiple floor divides, we await rounding:
    res /= 60
    if res <= MAX_MIN:
        res = round(res)
        return f"{res}m", f"{res} min{plural_suffix(res)}"

    res /= 60
    if res <= MAX_HOUR:
        res = round(res)
        return f"{res}h", f"{res} hour{plural_suffix(res)}"

    res = round(res / 24)
    return f"{res}d", f"{res} day{plural_suffix(res)}"


def plural_suffix(x):
    return "s" if x > 1 else ""


def pandas_ts_to_unix_ms(ts):
    return ts.value // int(1e6)
