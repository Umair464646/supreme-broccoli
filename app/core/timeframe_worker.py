from __future__ import annotations
from PyQt6.QtCore import QObject, pyqtSignal, pyqtSlot
from .resampler import build_timeframe
from .cache_manager import timeframe_cache_path
import pandas as pd

class TimeframeWorker(QObject):
    log = pyqtSignal(str, str)
    finished = pyqtSignal(str, object)
    error = pyqtSignal(str)

    def __init__(self, df, source_path: str, timeframe: str):
        super().__init__()
        self.df = df
        self.source_path = source_path
        self.timeframe = timeframe

    @pyqtSlot()
    def run(self):
        try:
            cache_path = timeframe_cache_path(self.source_path, self.timeframe)
            if cache_path.exists():
                self.log.emit("INFO", f"Loading timeframe cache: {cache_path.name}")
                out = pd.read_parquet(cache_path)
                self.log.emit("INFO", f"Loaded cached {self.timeframe}: {len(out):,} rows")
                self.finished.emit(self.timeframe, out)
                return

            self.log.emit("INFO", f"Building timeframe on demand: {self.timeframe}")
            out = build_timeframe(self.df, self.timeframe)
            try:
                out.to_parquet(cache_path, index=False)
                self.log.emit("INFO", f"Saved timeframe cache: {cache_path.name}")
            except Exception as exc:
                self.log.emit("WARN", f"Failed to save timeframe cache: {exc}")
            self.log.emit("INFO", f"Built {self.timeframe}: {len(out):,} rows")
            self.finished.emit(self.timeframe, out)
        except Exception as exc:
            self.log.emit("ERROR", f"Timeframe build failed for {self.timeframe}: {exc}")
            self.error.emit(str(exc))
