from __future__ import annotations

from PySide6.QtWidgets import QLabel, QWidget
from sqlalchemy import desc, select

from config.settings import MODEL_DIR
from database.connection import SessionLocal
from database.models import ModelMetric
from gui.widgets import ChartCanvas, make_table, page_header, section_title, set_cell, vertical


class AnalyticsPage(QWidget):
    def __init__(self):
        super().__init__()
        self.layout = vertical(self)
        self.layout.addLayout(page_header("Model analytics", "Compare supervised classifiers against unsupervised anomaly detection."))
        self.chart = ChartCanvas(self, (8, 3))
        self.layout.addWidget(self.chart)
        self.layout.addWidget(section_title("Evaluation metrics · held-out synthetic test set"))
        self.table = make_table(["Model", "Accuracy", "Precision", "Recall", "F1", "ROC-AUC", "TN", "FP", "FN", "TP"])
        self.layout.addWidget(self.table, 1)
        note = QLabel(f"Saved artifacts: {MODEL_DIR} · confusion matrices are shown in normal/anomaly label order.")
        note.setObjectName("muted")
        self.layout.addWidget(note)
        self.refresh()

    def refresh(self) -> None:
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