from __future__ import annotations

from collections import Counter

from PySide6.QtWidgets import QGridLayout, QHBoxLayout, QLabel, QTableWidget, QVBoxLayout, QWidget
from sqlalchemy import desc, select
from sqlalchemy.orm import joinedload

from database.connection import SessionLocal
from database.crud import get_dashboard_stats
from database.models import Alert, Anomaly, BehaviorEvent, RiskScore
from gui.widgets import ChartCanvas, make_table, page_header, section_title, set_cell, stat_card, vertical


class DashboardPage(QWidget):
    def __init__(self):
        super().__init__()
        self.layout = vertical(self)
        self.layout.addLayout(page_header("Security overview", "Behavioral activity and risk signals across the workspace."))
        cards = QGridLayout()
        cards.setSpacing(10)
        self.stats_labels = {}
        for index, (key, label, color) in enumerate([
            ("users", "Total users", "#087f8c"), ("events", "Events analyzed", "#3976a8"),
            ("anomalies", "Anomalies detected", "#cb8c32"), ("critical_alerts", "Open critical", "#b8494c"),
            ("average_risk", "Average risk", "#567d6e"),
        ]):
            card, value = stat_card(label, "0", color)
            self.stats_labels[key] = value
            cards.addWidget(card, 0, index)
        self.layout.addLayout(cards)
        second_row = QHBoxLayout()
        self.trend_chart = ChartCanvas(self, (6, 2.5))
        self.signal_chart = ChartCanvas(self, (5, 2.5))
        second_row.addWidget(self.trend_chart, 3)
        second_row.addWidget(self.signal_chart, 2)
        self.layout.addWidget(section_title("Risk activity · last 14 days"))
        self.layout.addLayout(second_row)
        self.layout.addWidget(section_title("Recent alerts"))
        self.alert_table = make_table(["Created", "Severity", "Signal", "Status"])
        self.layout.addWidget(self.alert_table, 1)
        self.refresh()

    def refresh(self) -> None:
        session = SessionLocal()
        try:
            stats = get_dashboard_stats(session)
            for key, label in self.stats_labels.items():
                label.setText(f"{stats[key]:,}")
            events = list(session.scalars(select(BehaviorEvent).options(joinedload(BehaviorEvent.risk_score)).order_by(desc(BehaviorEvent.timestamp)).limit(500)))
            buckets: dict[str, list[int]] = {}
            for event in events:
                key = event.timestamp.strftime("%b %d")
                buckets.setdefault(key, []).append(event.risk_score.score if event.risk_score else 0)
            self.trend_chart.axes.clear()
            labels = list(reversed(list(buckets.keys())[:14]))
            values = [sum(buckets[key]) / len(buckets[key]) for key in labels]
            self.trend_chart.axes.plot(labels, values, color="#087f8c", marker="o", linewidth=2)
            self.trend_chart.axes.fill_between(range(len(values)), values, color="#087f8c", alpha=.1)
            self.trend_chart.axes.set_ylabel("Mean risk")
            self.trend_chart.axes.set_ylim(0, 100)
            self.trend_chart.axes.grid(axis="y", color="#edf0f1")
            self.trend_chart.axes.tick_params(axis="x", rotation=25, labelsize=8)
            self.trend_chart.draw_idle()
            anomaly_rows = list(session.scalars(select(Anomaly).order_by(desc(Anomaly.created_at)).limit(300)))
            counts = Counter(indicator for row in anomaly_rows for indicator in (row.indicators or []))
            top = counts.most_common(5)
            self.signal_chart.axes.clear()
            if top:
                self.signal_chart.axes.barh([item[0] for item in reversed(top)], [item[1] for item in reversed(top)], color="#cb8c32")
            else:
                self.signal_chart.axes.text(.5, .5, "No anomaly indicators yet", ha="center", va="center", transform=self.signal_chart.axes.transAxes, color="#70828a")
            self.signal_chart.axes.grid(axis="x", color="#edf0f1")
            self.signal_chart.axes.tick_params(axis="y", labelsize=8)
            self.signal_chart.draw_idle()
            alerts = list(session.scalars(select(Alert).order_by(desc(Alert.created_at)).limit(8)))
            self.alert_table.setRowCount(len(alerts))
            for row, alert in enumerate(alerts):
                set_cell(self.alert_table, row, 0, alert.created_at.strftime("%Y-%m-%d %H:%M"))
                set_cell(self.alert_table, row, 1, alert.severity, {"CRITICAL": "#b8494c", "HIGH": "#cb8c32"}.get(alert.severity))
                set_cell(self.alert_table, row, 2, alert.title)
                set_cell(self.alert_table, row, 3, alert.status.title())
        finally:
            session.close()