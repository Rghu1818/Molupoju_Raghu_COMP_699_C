import numpy as np
import pandas as pd
from scipy import stats


def zscore_anomalies(series: pd.Series, z_thresh: float = 3.0) -> pd.DataFrame:
    if series is None or len(series) == 0:
        return pd.DataFrame({"idx": [], "value": [], "z": []})
    z = np.abs(stats.zscore(series, nan_policy="omit"))
    z = pd.Series(z, index=series.index)
    anom_idx = z[z > z_thresh].index
    return pd.DataFrame({
        "idx": anom_idx,
        "value": series.loc[anom_idx].values,
        "z": z.loc[anom_idx].values,
    })


def aggregate_timeseries(df: pd.DataFrame, ts_col: str, val_col: str, freq: str = "1H") -> pd.DataFrame:
    if df.empty:
        return df
    s = df.set_index(ts_col)[val_col].resample(freq).mean().dropna()
    return s.reset_index()
