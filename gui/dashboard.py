from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QFrame, QGridLayout, QHBoxLayout, QLabel, QPushButton, QScrollArea, QTableWidget, QVBoxLayout, QWidget
from sqlalchemy import desc, select
from sqlalchemy.orm import joinedload

from database.connection import SessionLocal
from database.crud import get_dashboard_stats, get_risk_distribution
from database.models import Alert, BehaviorEvent, RiskScore
from gui.widgets import ChartCanvas, make_table, page_header, section_title, set_cell, stat_card, vertical


class DashboardPage(QWidget):
    load_demo_requested = Signal()

    def __init__(self, user):
        super().__init__()
        self.user = user
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        page = QWidget()
        self.layout = vertical(page)
        scroll.setWidget(page)
        outer.addWidget(scroll)
        heading = QHBoxLayout()
        heading.addLayout(page_header("Security overview", "A clear view of behavioral activity, emerging risks, and analyst follow-up."), 1)
        demo_button = QPushButton("Load security demo")
        demo_button.clicked.connect(self.load_demo_requested.emit)
        heading.addWidget(demo_button, 0, Qt.AlignmentFlag.AlignBottom)
        self.layout.addLayout(heading)

        self.empty_state = QFrame()
        empty_layout = QHBoxLayout(self.empty_state)
        empty_layout.setContentsMargins(12, 8, 12, 8)
        empty_message = QLabel("No behavioral events available yet. Generate synthetic activity to begin analysis.")
        empty_message.setObjectName("muted")
        empty_layout.addWidget(empty_message, 1)
        empty_demo = QPushButton("Generate demo data")
        empty_demo.setObjectName("secondary")
        empty_demo.clicked.connect(self.load_demo_requested.emit)
        empty_layout.addWidget(empty_demo)
        self.layout.addWidget(self.empty_state)

        cards = QGridLayout()
        cards.setHorizontalSpacing(12)
        cards.setVerticalSpacing(12)
        self.stats_labels = {}
        for index, (key, label, color) in enumerate([
            ("users", "Total users", "#168c83"), ("events", "Events analyzed", "#4278b8"),
            ("anomalies", "Anomalies detected", "#d28a27"), ("critical_alerts", "Critical alerts", "#c94b5a"),
            ("average_risk", "Average risk score", "#627d69"), ("investigations", "Active investigations", "#547b91"),
        ]):
            card, value = stat_card(label, "0", color)
            self.stats_labels[key] = value
            cards.addWidget(card, index // 3, index % 3)
        self.layout.addLayout(cards)
        second_row = QHBoxLayout()
        second_row.setSpacing(12)
        trend_panel, self.trend_chart = self._chart_panel("Risk trend · last 14 days", (6, 2.6))
        distribution_panel, self.distribution_chart = self._chart_panel("Events by risk level", (5, 2.6))
        second_row.addWidget(trend_panel, 3)
        second_row.addWidget(distribution_panel, 2)
        self.layout.addLayout(second_row)
        self.layout.addWidget(section_title("Latest alerts"))
        self.alert_table = make_table(["Created", "Severity", "Signal", "Status"])
        self.layout.addWidget(self.alert_table, 1)
        self.refresh()

    def _chart_panel(self, title: str, size: tuple[float, float]) -> tuple[QFrame, ChartCanvas]:
        panel = QFrame()
        panel.setObjectName("chartPanel")
        panel.setStyleSheet("QFrame#chartPanel { background:white; border:1px solid #e4eaf0; border-radius:10px; }")
        panel_layout = QVBoxLayout(panel)
        panel_layout.setContentsMargins(14, 11, 14, 8)
        panel_layout.addWidget(section_title(title))
        chart = ChartCanvas(panel, size)
        panel_layout.addWidget(chart)
        return panel, chart

    def refresh(self) -> None:
        session = SessionLocal()
        try:
            stats = get_dashboard_stats(session)
            for key, label in self.stats_labels.items():
                value = stats[key]
                label.setText("—" if value is None else f"{value:,}")
            self.empty_state.setVisible(stats["events"] == 0)
            events = list(session.scalars(select(BehaviorEvent).options(joinedload(BehaviorEvent.risk_score)).order_by(desc(BehaviorEvent.timestamp)).limit(500)))
            buckets: dict[str, list[int]] = {}
            for event in events:
                if event.risk_score is not None:
                    key = event.timestamp.strftime("%b %d")
                    buckets.setdefault(key, []).append(event.risk_score.score)
            self.trend_chart.axes.clear()
            labels = list(reversed(list(buckets.keys())[:14]))
            values = [sum(buckets[key]) / len(buckets[key]) for key in labels]
            if values:
                self.trend_chart.axes.plot(labels, values, color="#087f8c", marker="o", linewidth=2)
                self.trend_chart.axes.fill_between(range(len(values)), values, color="#087f8c", alpha=.1)
                self.trend_chart.axes.set_ylabel("Risk score")
                self.trend_chart.axes.set_ylim(0, 100)
            else:
                self.trend_chart.axes.text(.5, .5, "No scored events available", ha="center", va="center", transform=self.trend_chart.axes.transAxes, color="#70828a")
            self._style_axes(self.trend_chart.axes, "y")
            self.trend_chart.draw_idle()
            levels = get_risk_distribution(session)
            self.distribution_chart.axes.clear()
            if sum(levels.values()):
                names = list(levels)
                values = [levels[name] for name in names]
                colors = ["#4b8b70", "#d3a042", "#d27b3b", "#bd4f58"]
                self.distribution_chart.axes.bar(names, values, color=colors)
                self.distribution_chart.axes.set_ylabel("Events")
            else:
                self.distribution_chart.axes.text(.5, .5, "No risk scores available", ha="center", va="center", transform=self.distribution_chart.axes.transAxes, color="#70828a")
            self._style_axes(self.distribution_chart.axes, "y")
            self.distribution_chart.axes.tick_params(axis="x", labelsize=7)
            self.distribution_chart.draw_idle()
            alerts = list(session.scalars(select(Alert).order_by(desc(Alert.created_at)).limit(8)))
            self.alert_table.setRowCount(len(alerts))
            for row, alert in enumerate(alerts):
                set_cell(self.alert_table, row, 0, alert.created_at.strftime("%Y-%m-%d %H:%M"))
                set_cell(self.alert_table, row, 1, alert.severity, {"CRITICAL": "#b8494c", "HIGH": "#cb8c32"}.get(alert.severity))
                set_cell(self.alert_table, row, 2, alert.title)
                set_cell(self.alert_table, row, 3, alert.status.title())
        finally:
            session.close()

    @staticmethod
    def _style_axes(axes, grid_axis: str) -> None:
        axes.grid(axis=grid_axis, color="#edf1f5")
        axes.tick_params(axis="x", rotation=20, labelsize=8, colors="#718294")
        axes.tick_params(axis="y", labelsize=8, colors="#718294")
        axes.spines[["top", "right"]].set_visible(False)
        axes.spines[["left", "bottom"]].set_color("#e2e9ef")
        axes.set_facecolor("white")