from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel, QTextEdit

class AILabPage(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        title = QLabel("AI Lab")
        title.setStyleSheet("font-size: 24px; font-weight: 700;")
        subtitle = QLabel("Feature Lab is now live. Real AI still comes later, after backtesting and validation.")
        subtitle.setWordWrap(True)
        subtitle.setStyleSheet("color: #8a95a5;")
        self.info = QTextEdit()
        self.info.setReadOnly(True)
        self.info.setPlainText("No dataset loaded yet.")
        layout.addWidget(title)
        layout.addWidget(subtitle)
        layout.addWidget(self.info)

    def set_dataframe(self, df):
        if df is None or df.empty:
            self.info.setPlainText("No dataset loaded yet.")
            return
        self.info.setPlainText("\n".join([
            f"Rows currently loaded: {len(df):,}",
            f"Columns currently loaded: {len(df.columns)}",
            f"Start: {df['timestamp'].iloc[0]}",
            f"End: {df['timestamp'].iloc[-1]}",
            "",
            "Current build policy:",
            "- optimized loading and charting",
            "- feature engine available",
            "- backtest engine next",
        ]))
