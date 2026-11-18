BG = "#111418"
SURFACE = "#191e24"
RAISED = "#222a33"
LINE = "#303a45"
TEXT = "#e7edf4"
MUTED = "#94a1af"
ACCENT = "#79a9df"
ACCENT_HI = "#9bc4f0"
UP = "#5fbd91"
DOWN = "#e07878"
GOLD = "#d5b36b"
PIE = ["#79a9df", "#5fbd91", "#d5b36b", "#a28bd5", "#e07878", "#5fb7bd", "#c18e70", "#94a1af"]
FONT = "'Inter', 'Segoe UI', Arial, sans-serif"
MONO = "'Cascadia Mono', 'Consolas', monospace"

STYLE = """
QWidget {
    color: %(TEXT)s;
    font-family: %(FONT)s;
    font-size: 13px;
}
QMainWindow, QDialog, QMessageBox, QWidget#Root {
    background: %(BG)s;
}
QToolTip {
    background: %(RAISED)s;
    color: %(TEXT)s;
    border: 1px solid %(LINE)s;
    padding: 6px 8px;
    border-radius: 5px;
}
QFrame#Sidebar {
    background: %(SURFACE)s;
    border: none;
    border-right: 1px solid %(LINE)s;
}
QLabel#Brand {
    font-size: 21px;
    font-weight: 750;
    letter-spacing: 0.5px;
    padding: 0 18px;
    color: %(TEXT)s;
}
QLabel#BrandCaption {
    color: %(MUTED)s;
    font-size: 10px;
    padding: 2px 18px 0 18px;
}
QLabel#Muted {
    color: %(MUTED)s;
    font-size: 11px;
    padding: 2px 0;
}
QLabel#PageTitle {
    font-size: 25px;
    font-weight: 700;
    color: %(TEXT)s;
    padding-bottom: 1px;
}
QLabel#PageSub {
    color: %(MUTED)s;
    font-size: 12px;
}
QLabel#Section {
    color: %(TEXT)s;
    font-size: 14px;
    font-weight: 650;
    padding-top: 9px;
    padding-bottom: 2px;
}
QPushButton {
    background: %(RAISED)s;
    border: 1px solid %(LINE)s;
    border-radius: 7px;
    padding: 8px 14px;
    min-height: 18px;
}
QPushButton:hover {
    background: #2a3541;
    border-color: #506174;
}
QPushButton:pressed {
    background: %(SURFACE)s;
}
QPushButton:disabled {
    color: #687481;
    background: %(SURFACE)s;
    border-color: %(LINE)s;
}
QPushButton#Nav {
    background: transparent;
    border: none;
    border-left: 3px solid transparent;
    border-radius: 0 7px 7px 0;
    color: %(MUTED)s;
    text-align: left;
    padding: 11px 15px;
    margin: 2px 9px 2px 0;
    min-height: 20px;
    font-weight: 550;
}
QPushButton#Nav:hover {
    color: %(TEXT)s;
    background: %(RAISED)s;
}
QPushButton#Nav:checked {
    color: %(TEXT)s;
    background: #273444;
    border-left: 3px solid %(ACCENT)s;
    font-weight: 700;
}
QPushButton#Action {
    background: #315f8f;
    border: 1px solid #4779a9;
    color: #ffffff;
    font-weight: 750;
}
QPushButton#Action:hover {
    background: #3d74aa;
    border-color: #6594c2;
    color: #ffffff;
}
QPushButton#Action:pressed {
    background: #274d75;
    border-color: #274d75;
    color: #ffffff;
}
QPushButton#Action:disabled {
    background: #303a45;
    border-color: #303a45;
    color: #aab4bf;
}
QWidget#ReportsPage, QWidget#ReportsBody {
    background: %(BG)s;
}
QPushButton#AccountAction {
    background: #79a9df;
    border: 1px solid #9bc4f0;
    border-radius: 8px;
    color: #101820;
    padding: 11px 20px;
    min-height: 20px;
    font-size: 14px;
    font-weight: 750;
}
QPushButton#AccountAction:hover {
    background: #9bc4f0;
    border-color: #b7d6f5;
    color: #101820;
}
QPushButton#AccountAction:pressed {
    background: #5f91c7;
    border-color: #5f91c7;
}
QPushButton#AccountAction:disabled {
    background: #303a45;
    border-color: #303a45;
    color: #8793a0;
}
QPushButton#Buy {
    background: rgba(95, 189, 145, 0.08);
    border: 1px solid %(UP)s;
    color: %(UP)s;
    font-weight: 700;
}
QPushButton#Buy:hover {
    background: %(UP)s;
    color: #101820;
}
QPushButton#Sell {
    background: rgba(224, 120, 120, 0.08);
    border: 1px solid %(DOWN)s;
    color: %(DOWN)s;
    font-weight: 700;
}
QPushButton#Sell:hover {
    background: %(DOWN)s;
    color: #101820;
}
QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox {
    background: %(BG)s;
    border: 1px solid %(LINE)s;
    border-radius: 7px;
    padding: 8px 10px;
    min-height: 19px;
    selection-background-color: %(ACCENT)s;
    selection-color: #101820;
}
QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus {
    border-color: %(ACCENT)s;
}
QDoubleSpinBox, QSpinBox {
    font-family: %(MONO)s;
}
QComboBox::drop-down {
    border: none;
    width: 25px;
}
QComboBox QAbstractItemView {
    background: %(RAISED)s;
    border: 1px solid %(LINE)s;
    selection-background-color: %(ACCENT)s;
    selection-color: #101820;
    outline: 0;
    padding: 4px;
}
QGroupBox {
    background: %(SURFACE)s;
    border: 1px solid %(LINE)s;
    border-radius: 10px;
    margin-top: 12px;
    padding: 20px 12px 12px 12px;
    font-weight: 600;
}
QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 12px;
    top: 0;
    padding: 0 5px;
    color: %(MUTED)s;
    background: %(SURFACE)s;
    font-size: 12px;
    font-weight: 600;
}
QFrame#Card {
    background: %(SURFACE)s;
    border: 1px solid %(LINE)s;
    border-radius: 9px;
}
QFrame#Metric, QFrame#Hero {
    background: %(SURFACE)s;
    border: 1px solid %(LINE)s;
    border-top: 3px solid %(LINE)s;
    border-radius: 9px;
}
QFrame#Hero {
    border-top: 3px solid %(ACCENT)s;
    background: #1b2530;
}
QFrame#Metric QLabel, QFrame#Hero QLabel {
    background: transparent;
}
QLabel#MetricTitle {
    color: %(MUTED)s;
    font-size: 11px;
    font-weight: 600;
}
QLabel#MetricValue {
    font-family: %(MONO)s;
    font-size: 21px;
    font-weight: 700;
    padding-top: 3px;
}
QTableWidget {
    background: transparent;
    alternate-background-color: #1d242c;
    border: none;
    gridline-color: transparent;
    outline: 0;
    selection-background-color: #2b3d50;
    selection-color: %(TEXT)s;
}
QTableWidget::item {
    border-bottom: 1px solid %(LINE)s;
    padding: 5px 8px;
}
QTableWidget::item:selected {
    background: #2b3d50;
    color: %(TEXT)s;
}
QTableWidget#StockQuotes {
    background: %(SURFACE)s;
    alternate-background-color: %(SURFACE)s;
}
QTableWidget#StockQuotes::item {
    background: %(SURFACE)s;
}
QTableWidget#StockQuotes::item:selected {
    background: #303b48;
    color: %(TEXT)s;
}
QHeaderView {
    background: transparent;
}
QHeaderView::section {
    background: %(RAISED)s;
    color: %(MUTED)s;
    padding: 9px 8px;
    border: none;
    border-bottom: 1px solid %(LINE)s;
    font-size: 11px;
    font-weight: 700;
}
QScrollArea, QAbstractScrollArea {
    background: %(BG)s;
    border: none;
}
QAbstractScrollArea > QWidget#qt_scrollarea_viewport {
    background: %(BG)s;
}
QTabWidget#ExchangeTabs::pane {
    background: %(SURFACE)s;
    border: 1px solid %(LINE)s;
    border-radius: 9px;
    top: -1px;
}
QTabWidget#ExchangeTabs QTabBar::tab {
    background: transparent;
    color: %(MUTED)s;
    border: none;
    border-bottom: 2px solid transparent;
    padding: 10px 24px;
    margin-right: 4px;
    font-weight: 650;
}
QTabWidget#ExchangeTabs QTabBar::tab:hover {
    color: %(TEXT)s;
    background: %(RAISED)s;
}
QTabWidget#ExchangeTabs QTabBar::tab:selected {
    color: %(TEXT)s;
    border-bottom: 2px solid %(ACCENT)s;
    background: %(RAISED)s;
}
QScrollBar:vertical {
    background: transparent;
    width: 9px;
    margin: 0;
}
QScrollBar::handle:vertical {
    background: %(LINE)s;
    min-height: 30px;
    border-radius: 4px;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0;
}
QScrollBar:horizontal {
    background: transparent;
    height: 9px;
}
QScrollBar::handle:horizontal {
    background: %(LINE)s;
    min-width: 30px;
    border-radius: 4px;
}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
    width: 0;
}
QFormLayout QLabel {
    color: %(MUTED)s;
}
""" % dict(BG=BG, SURFACE=SURFACE, RAISED=RAISED, LINE=LINE, TEXT=TEXT, MUTED=MUTED,
           ACCENT=ACCENT, ACCENT_HI=ACCENT_HI, UP=UP, DOWN=DOWN, FONT=FONT, MONO=MONO)
