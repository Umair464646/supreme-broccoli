from __future__ import annotations
import pandas as pd

TIMEFRAME_RULES = {
    "1s": "1s",
    "5s": "5s",
    "15s": "15s",
    "30s": "30s",
    "1m": "1min",
    "5m": "5min",
    "15m": "15min",
    "1h": "1h",
    "4h": "4h",
}

def build_timeframe(df: pd.DataFrame, timeframe: str) -> pd.DataFrame:
    if timeframe not in TIMEFRAME_RULES:
        raise ValueError(f"Unsupported timeframe: {timeframe}")
    if timeframe == "1s":
        return df.copy()
    local = df.copy().sort_values("timestamp").set_index("timestamp")
    agg = {"open":"first","high":"max","low":"min","close":"last","volume":"sum"}
    if "synthetic" in local.columns:
        agg["synthetic"] = "max"
    out = local.resample(TIMEFRAME_RULES[timeframe]).agg(agg)
    out = out.dropna(subset=["open","high","low","close"]).reset_index()
    return out
