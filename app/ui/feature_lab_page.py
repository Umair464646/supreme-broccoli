from __future__ import annotations
from pathlib import Path
from PyQt6.QtCore import pyqtSignal, QThread
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QCheckBox,
    QComboBox, QTextEdit, QProgressBar, QTableWidget, QTableWidgetItem,
    QFileDialog, QMessageBox
)
from app.core.feature_worker import FeatureWorker
from app.core.cache_manager import feature_export_dir

FEATURE_OPTIONS = [
    "EMA", "SMA", "RSI", "MACD", "ATR",
    "BOLLINGER", "VOLATILITY", "VOLUME_SPIKE",
    "BREAKOUT", "CANDLE_RATIOS"
]

class FeatureLabPage(QWidget):
    log_message = pyqtSignal(str, str)
    timeframe_requested = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.source_path = None
        self.timeframe_cache = {}
        self.feature_df = None
        self.generated_columns = []
        self.feature_thread = None
        self.feature_worker = None
        self.feature_checks = {}
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        title = QLabel("Feature Lab")
        title.setStyleSheet("font-size: 24px; font-weight: 700;")
        subtitle = QLabel("Choose a timeframe, choose feature groups, generate features, preview columns, and export the dataset.")
        subtitle.setWordWrap(True)
        subtitle.setStyleSheet("color: #8a95a5;")
        layout.addWidget(title)
        layout.addWidget(subtitle)

        top = QHBoxLayout()
        self.timeframe_box = QComboBox()
        self.timeframe_box.addItems(["1s","5s","15s","30s","1m","5m","15m","1h","4h"])
        self.timeframe_box.setCurrentText("1m")
        self.timeframe_box.currentTextChanged.connect(self._ensure_timeframe_ready)

        self.generate_btn = QPushButton("Generate Features")
        self.generate_btn.clicked.connect(self.generate_features)
        self.export_btn = QPushButton("Export Feature Dataset")
        self.export_btn.clicked.connect(self.export_features)
        self.export_btn.setEnabled(False)

        top.addWidget(QLabel("Timeframe"))
        top.addWidget(self.timeframe_box)
        top.addWidget(self.generate_btn)
        top.addWidget(self.export_btn)
        top.addStretch(1)
        layout.addLayout(top)

        features_row = QHBoxLayout()
        for name in FEATURE_OPTIONS:
            cb = QCheckBox(name)
            cb.setChecked(name in {"EMA", "RSI", "MACD", "ATR", "BOLLINGER", "VOLATILITY"})
            self.feature_checks[name] = cb
            features_row.addWidget(cb)
        layout.addLayout(features_row)

        self.stage_label = QLabel("Stage: idle")
        self.stage_label.setStyleSheet("color: #8a95a5;")
        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        layout.addWidget(self.stage_label)
        layout.addWidget(self.progress)

        self.summary_box = QTextEdit()
        self.summary_box.setReadOnly(True)
        self.summary_box.setMinimumHeight(120)
        layout.addWidget(self.summary_box)

        self.preview_table = QTableWidget(0, 0)
        layout.addWidget(self.preview_table, 1)

    def set_source_context(self, source_path: str, timeframe_cache: dict):
        self.source_path = source_path
        self.timeframe_cache = timeframe_cache
        self._refresh_summary()

    def set_timeframe_dataset(self, timeframe: str, df):
        self.timeframe_cache[timeframe] = df
        self._refresh_summary()

    def _ensure_timeframe_ready(self):
        tf = self.timeframe_box.currentText()
        if tf not in self.timeframe_cache:
            self.log_message.emit("INFO", f"Feature Lab requested timeframe build: {tf}")
            self.timeframe_requested.emit(tf)
        self._refresh_summary()

    def _selected_features(self):
        return [name for name, cb in self.feature_checks.items() if cb.isChecked()]

    def _refresh_summary(self):
        tf = self.timeframe_box.currentText()
        df = self.timeframe_cache.get(tf)
        lines = [f"Selected timeframe: {tf}"]
        if df is None:
            lines.append("Timeframe status: not loaded yet")
        else:
            lines.append(f"Timeframe rows: {len(df):,}")
            lines.append(f"Timeframe range: {df['timestamp'].iloc[0]} → {df['timestamp'].iloc[-1]}")
        selected = self._selected_features()
        lines.append(f"Selected feature groups: {', '.join(selected) if selected else 'none'}")
        if self.generated_columns:
            lines.append(f"Last generated columns: {len(self.generated_columns)}")
        self.summary_box.setPlainText("\n".join(lines))

    def generate_features(self):
        tf = self.timeframe_box.currentText()
        df = self.timeframe_cache.get(tf)
        selected = self._selected_features()

        if df is None:
            QMessageBox.warning(self, "Timeframe not ready", "Selected timeframe is not loaded yet.")
            return
        if not selected:
            QMessageBox.warning(self, "No features selected", "Select at least one feature group.")
            return

        self.generate_btn.setEnabled(False)
        self.export_btn.setEnabled(False)
        self.progress.setValue(0)
        self.stage_label.setText("Stage: preparing feature generation")

        self.feature_thread = QThread()
        self.feature_worker = FeatureWorker(df, selected)
        self.feature_worker.moveToThread(self.feature_thread)

        self.feature_thread.started.connect(self.feature_worker.run)
        self.feature_worker.progress.connect(self.progress.setValue)
        self.feature_worker.stage.connect(lambda t: self.stage_label.setText(f"Stage: {t}"))
        self.feature_worker.log.connect(self.log_message.emit)
        self.feature_worker.finished.connect(self._on_features_ready)
        self.feature_worker.error.connect(self._on_feature_error)

        self.feature_worker.finished.connect(self.feature_thread.quit)
        self.feature_worker.error.connect(self.feature_thread.quit)
        self.feature_thread.finished.connect(self._cleanup_feature_worker)

        self.feature_thread.start()

    def _on_features_ready(self, df, generated_columns):
        self.feature_df = df
        self.generated_columns = generated_columns
        self.generate_btn.setEnabled(True)
        self.export_btn.setEnabled(True)
        self._refresh_summary()
        self._populate_preview(df, generated_columns)

    def _on_feature_error(self, text: str):
        self.generate_btn.setEnabled(True)
        self.progress.setValue(0)
        self.stage_label.setText("Stage: generation failed")
        QMessageBox.critical(self, "Feature generation failed", text)

    def _cleanup_feature_worker(self):
        self.feature_worker = None
        self.feature_thread = None

    def _populate_preview(self, df, generated_columns):
        preview_cols = ["timestamp", "open", "high", "low", "close", "volume"]
        for col in generated_columns[:12]:
            if col not in preview_cols:
                preview_cols.append(col)
        preview_df = df[preview_cols].tail(20).reset_index(drop=True)

        self.preview_table.setRowCount(len(preview_df))
        self.preview_table.setColumnCount(len(preview_df.columns))
        self.preview_table.setHorizontalHeaderLabels(list(preview_df.columns))
        for r in range(len(preview_df)):
            for c, col in enumerate(preview_df.columns):
                val = preview_df.iloc[r, c]
                self.preview_table.setItem(r, c, QTableWidgetItem("" if val is None else str(val)))
        self.preview_table.resizeColumnsToContents()

    def export_features(self):
        if self.feature_df is None or self.feature_df.empty:
            return
        default_dir = str(feature_export_dir(self.source_path)) if self.source_path else ""
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Export feature dataset",
            str(Path(default_dir) / f"features_{self.timeframe_box.currentText()}.parquet"),
            "Parquet Files (*.parquet);;CSV Files (*.csv)"
        )
        if not path:
            return
        try:
            if path.lower().endswith(".csv"):
                self.feature_df.to_csv(path, index=False)
            else:
                if not path.lower().endswith(".parquet"):
                    path = path + ".parquet"
                self.feature_df.to_parquet(path, index=False)
            self.log_message.emit("INFO", f"Exported feature dataset: {path}")
            QMessageBox.information(self, "Export complete", f"Feature dataset saved to:\n{path}")
        except Exception as exc:
            QMessageBox.critical(self, "Export failed", str(exc))
