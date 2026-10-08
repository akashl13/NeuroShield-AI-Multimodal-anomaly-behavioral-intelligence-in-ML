from __future__ import annotations

from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.figure import Figure
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget


def page_header(title: str, subtitle: str) -> QVBoxLayout:
    layout = QVBoxLayout()
    eyebrow = QLabel("NEUROSHIELD / OPERATIONS")
    eyebrow.setObjectName("eyebrow")
    heading = QLabel(title)
    heading.setObjectName("pageTitle")
    detail = QLabel(subtitle)
    detail.setObjectName("muted")
    layout.addWidget(eyebrow)
    layout.addWidget(heading)
    layout.addWidget(detail)
    layout.addSpacing(10)
    return layout


def stat_card(label: str, value: str = "0", accent: str = "#087f8c") -> tuple[QFrame, QLabel]:
    card = QFrame()
    card.setObjectName("statCard")
    card.setStyleSheet(f"""
        QFrame#statCard {{ background: #ffffff; border: 1px solid #e4eaf0; border-top: 3px solid {accent}; border-radius: 10px; }}
        QFrame#statCard QLabel {{ border: 0; }}
    """)
    layout = QVBoxLayout(card)
    layout.setContentsMargins(15, 13, 15, 14)
    layout.setSpacing(8)
    title = QLabel(label)
    title.setStyleSheet("color:#718294;font-size:11px;font-weight:600;border:0")
    number = QLabel(value)
    number.setStyleSheet("color:#142738;font-size:27px;font-weight:700;border:0")
    layout.addWidget(title)
    layout.addWidget(number)
    return card, number


def make_table(headers: list[str]) -> QTableWidget:
    table = QTableWidget(0, len(headers))
    table.setHorizontalHeaderLabels(headers)
    table.setAlternatingRowColors(True)
    table.setShowGrid(False)
    table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
    table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
    table.verticalHeader().setVisible(False)
    table.verticalHeader().setDefaultSectionSize(38)
    table.horizontalHeader().setStretchLastSection(True)
    return table


def set_cell(table: QTableWidget, row: int, column: int, value: object, color: str | None = None) -> None:
    item = QTableWidgetItem(str(value))
    item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
    if color:
        item.setForeground(Qt.GlobalColor.white)
        item.setBackground(__import__("PySide6.QtGui", fromlist=["QColor"]).QColor(color))
    table.setItem(row, column, item)


class ChartCanvas(FigureCanvasQTAgg):
    def __init__(self, parent: QWidget | None = None, figsize: tuple[float, float] = (6, 2.5)):
        figure = Figure(figsize=figsize, dpi=100, facecolor="white", tight_layout=True)
        self.axes = figure.add_subplot(111)
        super().__init__(figure)
        self.setParent(parent)
        self.setMinimumHeight(190)


def section_title(text: str) -> QLabel:
    label = QLabel(text)
    label.setStyleSheet("font-size:14px;font-weight:700;color:#263a43;padding:4px 0")
    return label


def horizontal() -> QHBoxLayout:
    layout = QHBoxLayout()
    layout.setSpacing(12)
    return layout


def vertical(container: QWidget) -> QVBoxLayout:
    layout = QVBoxLayout(container)
    layout.setContentsMargins(22, 18, 22, 18)
    layout.setSpacing(12)
    return layout