from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta, timezone

from PySide6.QtWidgets import QComboBox, QHBoxLayout, QLabel, QTabWidget, QVBoxLayout, QWidget
from sqlalchemy import desc, select
from sqlalchemy.orm import joinedload

from config.settings import MODEL_DIR
from database.connection import SessionLocal
from database.models import BehaviorEvent, ModelMetric
from gui.widgets import ChartCanvas, make_table, page_header, section_title, set_cell, vertical


class AnalyticsPage(QWidget):
    def __init__(self):
        super().__init__()
        self.layout = vertical(self)
        self.layout.addLayout(page_header("Security analytics", "Explore observed activity and compare stored model evaluation results."))
        self.tabs = QTabWidget()
        self.layout.addWidget(self.tabs, 1)

        behavior_tab = QWidget()
        behavior_layout = QVBoxLayout(behavior_tab)
        controls = QHBoxLayout()
        controls.addWidget(section_title("Behavior over time"), 1)
        self.range_filter = QComboBox()
        self.range_filter.addItem("Last 24 hours", 24)
        self.range_filter.addItem("Last 7 days", 7 * 24)
        self.range_filter.addItem("Last 30 days", 30 * 24)
        self.range_filter.addItem("Last 90 days", 90 * 24)
        controls.addWidget(self.range_filter)
        behavior_layout.addLayout(controls)
        self.event_summary = QLabel()
        self.event_summary.setObjectName("muted")
        behavior_layout.addWidget(self.event_summary)
        chart_row = QHBoxLayout()
        self.activity_chart = ChartCanvas(self, (6, 2.8))
        self.risk_chart = ChartCanvas(self, (6, 2.8))
        chart_row.addWidget(self.activity_chart, 1)
        chart_row.addWidget(self.risk_chart, 1)
        behavior_layout.addLayout(chart_row, 1)
        self.behavior_empty = QLabel("No behavioral events available yet. Generate synthetic activity to begin analysis.")
        self.behavior_empty.setObjectName("muted")
        behavior_layout.addWidget(self.behavior_empty)
        self.tabs.addTab(behavior_tab, "Behavior analytics")

        model_tab = QWidget()
        model_layout = QVBoxLayout(model_tab)
        self.chart = ChartCanvas(self, (8, 3))
        model_layout.addWidget(self.chart)
        model_layout.addWidget(section_title("Evaluation metrics · held-out synthetic test set"))
        self.table = make_table(["Model", "Accuracy", "Precision", "Recall", "F1", "ROC-AUC", "TN", "FP", "FN", "TP"])
        model_layout.addWidget(self.table, 1)
        note = QLabel(f"Saved artifacts: {MODEL_DIR} · confusion matrices are shown in normal/anomaly label order.")
        note.setObjectName("muted")
        model_layout.addWidget(note)
        self.tabs.addTab(model_tab, "Model performance")
        self.range_filter.currentIndexChanged.connect(self.refresh_behavior)
        self.refresh()

    def refresh(self) -> None:
        self.refresh_model_metrics()
        self.refresh_behavior()

    def refresh_model_metrics(self) -> None:
        session = SessionLocal()
        try:
            rows = list(session.scalars(select(ModelMetric).order_by(desc(ModelMetric.trained_at))))
            latest = {}
            for metric in rows:
                latest.setdefault(metric.model_name, metric)
            metrics = list(latest.values())
            self.table.setRowCount(len(metrics))
            for row, metric in enumerate(metrics):
                matrix = metric.confusion_matrix or [[0, 0], [0, 0]]
                values = [metric.model_name.replace("_", " ").title(), f"{metric.accuracy:.3f}", f"{metric.precision:.3f}", f"{metric.recall:.3f}", f"{metric.f1:.3f}", f"{metric.roc_auc:.3f}", matrix[0][0], matrix[0][1], matrix[1][0], matrix[1][1]]
                for column, value in enumerate(values):
                    set_cell(self.table, row, column, value)
            self.chart.axes.clear()
            if metrics:
                names = [metric.model_name.replace("_", " ").title() for metric in metrics]
                positions = list(range(len(names)))
                self.chart.axes.bar([position - .18 for position in positions], [metric.f1 for metric in metrics], width=.36, label="F1", color="#087f8c")
                self.chart.axes.bar([position + .18 for position in positions], [metric.roc_auc for metric in metrics], width=.36, label="ROC-AUC", color="#cb8c32")
                self.chart.axes.set_xticks(positions, names, rotation=15, ha="right")
                self.chart.axes.set_ylim(0, 1.05)
                self.chart.axes.legend(frameon=False, ncols=2, loc="lower right")
                self.chart.axes.grid(axis="y", color="#edf0f1")
            else:
                self.chart.axes.text(.5, .5, "Train models in Settings to populate the comparison.", ha="center", va="center", transform=self.chart.axes.transAxes, color="#70828a")
            self.chart.draw_idle()
        finally:
            session.close()

    def refresh_behavior(self, *_args) -> None:
        hours = int(self.range_filter.currentData())
        cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
        session = SessionLocal()
        try:
            events = list(session.scalars(
                select(BehaviorEvent)
                .options(joinedload(BehaviorEvent.risk_score), joinedload(BehaviorEvent.anomaly))
                .where(BehaviorEvent.timestamp >= cutoff)
                .order_by(BehaviorEvent.timestamp)
                .limit(10_000)
            ))
            self.behavior_empty.setVisible(not events)
            if not events:
                self.event_summary.setText("0 events in the selected window")
                self._draw_timeline(self.activity_chart.axes, {}, "Events")
                self._draw_timeline(self.risk_chart.axes, {}, "Average risk")
                self.activity_chart.draw_idle()
                self.risk_chart.draw_idle()
                return

            buckets: dict[str, list[BehaviorEvent]] = defaultdict(list)
            for event in events:
                timestamp = event.timestamp
                if timestamp.tzinfo is None:
                    timestamp = timestamp.replace(tzinfo=timezone.utc)
                bucket = timestamp.strftime("%b %d %H:00" if hours <= 24 else "%b %d")
                buckets[bucket].append(event)
            event_counts = {label: len(items) for label, items in buckets.items()}
            risk_averages = {
                label: sum(event.risk_score.score for event in items if event.risk_score)
                / sum(1 for event in items if event.risk_score)
                for label, items in buckets.items()
                if any(event.risk_score for event in items)
            }
            anomaly_count = sum(bool(event.anomaly and event.anomaly.detected) for event in events)
            scored_count = sum(event.risk_score is not None for event in events)
            self.event_summary.setText(
                f"{len(events):,} events · {anomaly_count:,} anomalies · "
                f"{scored_count:,} events with risk scores in the selected window"
            )
            self._draw_timeline(self.activity_chart.axes, event_counts, "Events")
            self._draw_timeline(self.risk_chart.axes, risk_averages, "Average risk", (0, 100))
            self.activity_chart.draw_idle()
            self.risk_chart.draw_idle()
        finally:
            session.close()

    @staticmethod
    def _draw_timeline(axes, values: dict[str, float], label: str, limits: tuple[int, int] | None = None) -> None:
        axes.clear()
        if values:
            labels = list(values)
            scores = [values[item] for item in labels]
            axes.plot(labels, scores, color="#087f8c", marker="o", linewidth=1.8)
            axes.fill_between(range(len(scores)), scores, color="#087f8c", alpha=.1)
            axes.set_ylabel(label)
            if limits:
                axes.set_ylim(*limits)
        else:
            axes.text(.5, .5, "No scored events available", ha="center", va="center", transform=axes.transAxes, color="#70828a")
        axes.grid(axis="y", color="#edf1f5")
        axes.tick_params(axis="x", rotation=25, labelsize=7, colors="#718294")
        axes.tick_params(axis="y", labelsize=8, colors="#718294")
        axes.spines[["top", "right"]].set_visible(False)
        axes.spines[["left", "bottom"]].set_color("#e2e9ef")
        axes.set_facecolor("white")