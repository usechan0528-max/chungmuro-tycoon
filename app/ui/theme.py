from __future__ import annotations

REPORT_STYLE_SHEET = """
QMainWindow, QWidget {
    background: #111418;
    color: #e4e7eb;
    font-family: "Malgun Gothic", "Segoe UI", sans-serif;
    font-size: 13px;
}

QLabel#Title {
    font-size: 30px;
    font-weight: 700;
    color: #f3f5f7;
    padding-bottom: 2px;
}

QLabel#Subtitle {
    font-size: 14px;
    color: #aeb7c2;
}

QLabel#ScreenTitle {
    font-size: 19px;
    font-weight: 700;
    color: #f0f3f6;
    border-bottom: 1px solid #303843;
    padding: 8px 0 10px 0;
}

QLabel#SectionTitle {
    font-size: 15px;
    font-weight: 700;
    color: #d7dde4;
    padding: 8px 0 4px 0;
}

QLabel#PanelText {
    background: #181c21;
    border: 1px solid #2c333d;
    border-radius: 3px;
    padding: 10px;
    color: #d9dee5;
}

QGroupBox {
    background: #151a20;
    border: 1px solid #2c333d;
    border-radius: 3px;
    margin-top: 12px;
    padding: 12px;
    font-weight: 700;
    color: #d7dde4;
}

QGroupBox::title {
    subcontrol-origin: margin;
    left: 10px;
    padding: 0 4px;
    color: #c4ccd6;
}

QFrame#CandidateCard {
    background: #111820;
    border: 1px solid #344150;
    border-radius: 4px;
    padding: 8px;
}

QFrame#GlobalNav {
    background: #141920;
    border-bottom: 1px solid #2c333d;
}

QLabel#CardTitle {
    font-size: 15px;
    font-weight: 700;
    color: #f0f3f6;
    padding-bottom: 4px;
}

QLabel#NavTitle {
    color: #c4ccd6;
    font-weight: 700;
}

QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox, QTextEdit, QListWidget, QTableWidget {
    background: #0f1317;
    border: 1px solid #313944;
    border-radius: 2px;
    padding: 7px;
    color: #e7ebef;
    selection-background-color: #49657e;
    selection-color: #ffffff;
}

QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox {
    min-height: 28px;
}

QListWidget::item {
    border-bottom: 1px solid #252b33;
    padding: 7px;
}

QListWidget::item:selected {
    background: #253544;
    color: #ffffff;
}

QTableWidget {
    gridline-color: #252b33;
}

QTableWidget::item {
    padding: 6px;
}

QTableWidget::item:selected {
    background: #253544;
    color: #ffffff;
}

QHeaderView::section {
    background: #1a2028;
    color: #d7dde4;
    border: 1px solid #2c333d;
    padding: 7px;
    font-weight: 700;
}

QTabWidget::pane {
    border: 1px solid #2c333d;
    background: #151a20;
    top: -1px;
}

QTabBar::tab {
    background: #1a2028;
    border: 1px solid #2c333d;
    padding: 8px 12px;
    color: #c4ccd6;
}

QTabBar::tab:selected {
    background: #253544;
    color: #ffffff;
    border-color: #4b5c6e;
}

QPushButton {
    background: #222a33;
    border: 1px solid #3a4653;
    border-radius: 3px;
    padding: 8px 11px;
    color: #e9edf2;
    font-weight: 600;
}

QPushButton:hover {
    background: #2c3743;
    border-color: #536273;
}

QPushButton:pressed {
    background: #1b222a;
}

QPushButton:disabled {
    background: #171b20;
    border-color: #282f38;
    color: #6f7782;
}

QPushButton#NavButton {
    min-height: 30px;
    max-height: 30px;
    padding: 4px 12px;
}

QPushButton#ChoiceTile {
    min-height: 44px;
    max-height: 44px;
    padding: 7px 10px;
    text-align: center;
}

QPushButton#ChoiceTile:checked {
    background: #2b3947;
    border: 1px solid #6f8297;
    padding: 7px 10px;
    color: #ffffff;
}

QPushButton#ChoiceTile:hover:checked {
    background: #314253;
    border-color: #8196ad;
}

QLabel#MutedText {
    color: #aeb7c2;
    padding: 2px 0;
}

QScrollArea {
    border: 0;
}

QMessageBox {
    background: #111418;
}
"""
