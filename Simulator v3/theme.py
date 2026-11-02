BG, SURFACE, RAISED, LINE = "#181a1d", "#202327", "#2a2e33", "#33383e"
TEXT, MUTED = "#dde0e4", "#8a9097"
ACCENT, ACCENT_HI = "#6f9bd1", "#9bbbe0"
UP, DOWN, GOLD = "#5aa97a", "#c9605a", "#c9a24d"
PIE = ["#6f9bd1", "#5aa97a", "#c9a24d", "#8f7fc4", "#c9605a", "#5fb0b3", "#b08968", "#8a9097"]
FONT = "'Segoe UI','Helvetica Neue',Arial,sans-serif"
MONO = "Consolas,'Courier New',monospace"

STYLE = """
QWidget { color:%(TEXT)s; font-family:%(FONT)s; font-size:13px; }
QMainWindow, QDialog, QMessageBox, QWidget#Root { background:%(BG)s; }
QToolTip { background:%(RAISED)s; color:%(TEXT)s; border:1px solid %(LINE)s; padding:3px; }
QFrame#Sidebar { background:%(SURFACE)s; border:none; border-right:1px solid %(LINE)s; }
QLabel#Brand { font-size:16px; font-weight:600; padding:0 12px; }
QLabel#Muted { color:%(MUTED)s; font-size:11px; padding:0 12px; }
QLabel#PageTitle { font-size:20px; font-weight:600; }
QLabel#PageSub { color:%(MUTED)s; }
QLabel#Section { color:%(MUTED)s; padding-top:8px; }
QPushButton { background:%(RAISED)s; border:1px solid %(LINE)s; border-radius:3px; padding:7px 14px; }
QPushButton:hover { border-color:%(MUTED)s; }
QPushButton#Nav { background:transparent; border:none; border-left:2px solid transparent; border-radius:0; color:%(MUTED)s; text-align:left; padding:9px 12px; }
QPushButton#Nav:hover { color:%(TEXT)s; background:%(RAISED)s; }
QPushButton#Nav:checked { color:%(TEXT)s; background:%(RAISED)s; border-left:2px solid %(ACCENT)s; }
QPushButton#Action { background:%(ACCENT)s; border:1px solid %(ACCENT)s; color:#101316; font-weight:600; }
QPushButton#Action:hover { background:%(ACCENT_HI)s; border-color:%(ACCENT_HI)s; }
QPushButton#Buy { background:transparent; border:1px solid %(UP)s; color:%(UP)s; font-weight:600; }
QPushButton#Buy:hover { background:%(UP)s; color:#101316; }
QPushButton#Sell { background:transparent; border:1px solid %(DOWN)s; color:%(DOWN)s; font-weight:600; }
QPushButton#Sell:hover { background:%(DOWN)s; color:#101316; }
QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox { background:%(BG)s; border:1px solid %(LINE)s; border-radius:3px; padding:5px 8px; selection-background-color:%(ACCENT)s; selection-color:#101316; }
QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus { border-color:%(ACCENT)s; }
QDoubleSpinBox, QSpinBox { font-family:%(MONO)s; }
QComboBox::drop-down { border:none; width:22px; }
QComboBox QAbstractItemView { background:%(RAISED)s; border:1px solid %(LINE)s; selection-background-color:%(ACCENT)s; selection-color:#101316; outline:0; }
QGroupBox { background:%(SURFACE)s; border:1px solid %(LINE)s; border-radius:4px; margin-top:0; padding-top:34px; }
QGroupBox::title { subcontrol-origin:padding; subcontrol-position:top left; padding:10px 14px; color:%(MUTED)s; }
QFrame#Card { background:%(SURFACE)s; border:1px solid %(LINE)s; border-radius:4px; }
QFrame#Metric, QFrame#Hero { background:%(SURFACE)s; border:none; border-top:2px solid %(LINE)s; border-radius:0; }
QFrame#Hero { border-top:2px solid %(ACCENT)s; }
QFrame#Metric QLabel, QFrame#Hero QLabel { background:transparent; }
QLabel#MetricTitle { color:%(MUTED)s; }
QLabel#MetricValue { font-family:%(MONO)s; font-size:22px; }
QTableWidget { background:transparent; border:none; gridline-color:transparent; outline:0; }
QTableWidget::item { border-bottom:1px solid %(LINE)s; padding:0 8px; }
QTableWidget::item:selected { background:%(RAISED)s; color:%(TEXT)s; }
QHeaderView { background:transparent; }
QHeaderView::section { background:transparent; color:%(MUTED)s; padding:8px; border:none; border-bottom:1px solid %(MUTED)s; text-align:left; }
QScrollBar:vertical { background:transparent; width:9px; margin:0; }
QScrollBar::handle:vertical { background:%(LINE)s; min-height:30px; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height:0; }
QScrollBar:horizontal { background:transparent; height:9px; }
QScrollBar::handle:horizontal { background:%(LINE)s; min-width:30px; }
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width:0; }
""" % dict(BG=BG, SURFACE=SURFACE, RAISED=RAISED, LINE=LINE, TEXT=TEXT, MUTED=MUTED, ACCENT=ACCENT,
           ACCENT_HI=ACCENT_HI, UP=UP, DOWN=DOWN, FONT=FONT, MONO=MONO)
