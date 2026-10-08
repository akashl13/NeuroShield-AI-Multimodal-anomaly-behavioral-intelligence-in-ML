APP_STYLE = """
QWidget { background: #f3f6fa; color: #172b3a; font-family: 'DejaVu Sans'; font-size: 13px; }
QMainWindow, QDialog { background: #f3f6fa; }
QLabel#eyebrow { color: #168c83; font-size: 10px; font-weight: 700; letter-spacing: 1px; }
QLabel#pageTitle { color: #142738; font-size: 25px; font-weight: 700; }
QLabel#muted { color: #718294; }
QFrame#sidebar { background: #102333; border: none; }
QFrame#sidebar QLabel { color: #e8f0f5; }
QFrame#topbar { background: #ffffff; border-bottom: 1px solid #e3eaf0; }
QPushButton { background: #087f78; color: white; border: 0; border-radius: 7px; padding: 10px 16px; font-weight: 600; }
QPushButton:hover { background: #066d68; }
QPushButton:pressed { background: #075d59; }
QPushButton:disabled { background: #bdcbd0; }
QPushButton#secondary { background: #e9eff3; color: #294356; }
QPushButton#secondary:hover { background: #dce7ed; }
QPushButton#danger { background: #b84050; }
QPushButton#danger:hover { background: #a33344; }
QPushButton#nav { background: transparent; color: #aabdc9; text-align: left; padding: 12px 14px; border-radius: 7px; }
QPushButton#nav:hover { background: #1b3648; color: white; }
QPushButton#nav:checked { background: #1b4853; color: #8ce0d0; }
QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox, QTextEdit { background: white; border: 1px solid #d6e0e7; border-radius: 7px; padding: 9px; selection-background-color: #087f78; }
QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus, QTextEdit:focus { border: 1px solid #168c83; }
QTableWidget { background: white; alternate-background-color: #f7f9fb; border: 1px solid #e4eaf0; gridline-color: #edf1f5; border-radius: 9px; selection-background-color: #e2f3f1; selection-color: #173b40; }
QHeaderView::section { background: #f2f6f8; color: #586c7c; border: 0; border-bottom: 1px solid #e4eaf0; padding: 10px 8px; font-weight: 600; }
QTableCornerButton::section { background: #f2f6f8; border: 0; }
QProgressBar { background: #e7edef; border: 0; border-radius: 4px; height: 12px; text-align: center; }
QProgressBar::chunk { background: #e4a23b; border-radius: 4px; }
QTabWidget::pane { border: 1px solid #dfe6e8; background: white; }
QTabBar::tab { padding: 9px 15px; }
QScrollBar:vertical { background: transparent; width: 10px; margin: 2px; }
QScrollBar::handle:vertical { background: #ccd7df; min-height: 28px; border-radius: 5px; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
"""