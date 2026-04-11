from __future__ import annotations
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import List, Tuple
import pandas as pd
import pyarrow.parquet as pq
from .schema import REQUIRED_COLUMNS, MINIMAL_COLUMNS

@dataclass
class DataProfile:
    path: str
    rows: int
    start: str
    end: str
    zero_volume_pct: float
    synthetic_pct: float
    duplicate_timestamps: int
    columns: List[str]
    warnings: List[str]

def normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out.columns = [str(c).strip().lower() for c in out.columns]
    return out

def load_csv_minimal(path: str) -> pd.DataFrame:
    needed = set(MINIMAL_COLUMNS)
    return pd.read_csv(path, usecols=lambda c: str(c).strip().lower() in needed)

def load_parquet_minimal(path: str) -> pd.DataFrame:
    raw_names = pq.ParquetFile(path).schema.names
    selected = [c for c in raw_names if str(c).strip().lower() in set(MINIMAL_COLUMNS)]
    if not selected:
        raise ValueError("No required columns found in Parquet file")
    return pd.read_parquet(path, columns=selected)

def load_parquet_date_window(path: str, start=None, end=None) -> pd.DataFrame:
    raw_names = pq.ParquetFile(path).schema.names
    selected = [c for c in raw_names if str(c).strip().lower() in set(MINIMAL_COLUMNS)]
    if not selected:
        raise ValueError("No required columns found in Parquet file")
    df = pd.read_parquet(path, columns=selected)
    df = normalize_columns(df)
    df = parse_timestamp_column(df)
    df = convert_numeric_columns(df)
    if start is not None:
        df = df[df["timestamp"] >= pd.Timestamp(start, tz="UTC")]
    if end is not None:
        df = df[df["timestamp"] <= pd.Timestamp(end, tz="UTC")]
    return df.sort_values("timestamp").reset_index(drop=True)

def parse_timestamp_column(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    if "timestamp" not in out.columns:
        for alt in ["time", "datetime", "date"]:
            if alt in out.columns:
                out = out.rename(columns={alt: "timestamp"})
                break
    if "timestamp" not in out.columns:
        raise ValueError("Missing timestamp column")
    out["timestamp"] = pd.to_datetime(out["timestamp"], utc=True, errors="coerce")
    return out

def convert_numeric_columns(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    for c in ["open", "high", "low", "close", "volume", "synthetic"]:
        if c in out.columns:
            out[c] = pd.to_numeric(out[c], errors="coerce")
    if "synthetic" in out.columns:
        out["synthetic"] = out["synthetic"].fillna(0).astype(int)
    return out

def validate_dataframe(df: pd.DataFrame) -> Tuple[bool, List[str]]:
    warnings: List[str] = []
    missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    if missing:
        return False, [f"Missing required columns: {', '.join(missing)}"]
    if df["timestamp"].isna().any():
        return False, ["Some timestamps are null after parsing"]
    if df[["open","high","low","close","volume"]].isna().any().any():
        warnings.append("Some OHLCV values are null")
    if (df["high"] < df["low"]).any():
        warnings.append("Some rows have high lower than low")
    return True, warnings

def profile_dataframe(df: pd.DataFrame, path: str, warnings: List[str]) -> DataProfile:
    zero_volume_pct = float((df["volume"].fillna(0) == 0).mean() * 100)
    synthetic_pct = float((df["synthetic"].fillna(0) == 1).mean() * 100) if "synthetic" in df.columns else 0.0
    dupes = int(df["timestamp"].duplicated().sum())
    return DataProfile(
        path=str(path),
        rows=len(df),
        start=str(df["timestamp"].min()),
        end=str(df["timestamp"].max()),
        zero_volume_pct=zero_volume_pct,
        synthetic_pct=synthetic_pct,
        duplicate_timestamps=dupes,
        columns=list(df.columns),
        warnings=warnings,
    )

def load_market_file_minimal(path: str | Path):
    path = str(path)
    suffix = Path(path).suffix.lower()
    if suffix == ".csv":
        df = load_csv_minimal(path)
    elif suffix in {".parquet", ".pq"}:
        df = load_parquet_minimal(path)
    else:
        raise ValueError("Unsupported file type. Use CSV or Parquet.")
    df = normalize_columns(df)
    df = parse_timestamp_column(df)
    df = convert_numeric_columns(df)
    df = df.sort_values("timestamp").reset_index(drop=True)
    ok, warnings = validate_dataframe(df)
    if not ok:
        raise ValueError("; ".join(warnings))
    return df, profile_dataframe(df, path, warnings)

def profile_to_text(profile: DataProfile) -> str:
    lines = [
        f"Path: {profile.path}",
        f"Rows: {profile.rows:,}",
        f"Start: {profile.start}",
        f"End: {profile.end}",
        f"Zero-volume bars: {profile.zero_volume_pct:.2f}%",
        f"Synthetic rows: {profile.synthetic_pct:.2f}%",
        f"Duplicate timestamps: {profile.duplicate_timestamps}",
        f"Columns loaded: {', '.join(profile.columns)}",
    ]
    if profile.warnings:
        lines.append("")
        lines.append("Warnings:")
        lines.extend(f"- {w}" for w in profile.warnings)
    return "\n".join(lines)

def profile_to_dict(profile: DataProfile) -> dict:
    return asdict(profile)
