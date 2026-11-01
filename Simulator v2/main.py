import sys
from PyQt6.QtWidgets import QApplication, QMainWindow, QWidget, QHBoxLayout, QVBoxLayout, QPushButton, QLabel, QStackedWidget, QFrame
from PyQt6.QtCore import Qt
from database import init_db
from pages import DashboardPage, AccountPage, PortfolioPage, DepositPage, SimulationPage, ReportsPage, StockMarketPage

APP_STYLE = """
QWidget { background: #111416; color: #e6ecec; font-family: Consolas, 'Courier New'; font-size: 12px; }
QMainWindow { background: #111416; }
QFrame#Sidebar { background: #171b1e; border-right: 1px solid #30383b; }
QLabel#Brand { color: #73e0bd; font-size: 18px; font-weight: bold; padding: 8px 4px 16px 4px; }
QLabel#Muted { color: #8b999c; }
QPushButton { background: #202629; color: #dce5e5; border: 1px solid #303a3e; padding: 9px 10px; text-align: left; }
QPushButton:hover { background: #293337; border-color: #73e0bd; }
QPushButton:checked { background: #203a34; color: #86f0ca; border: 1px solid #477e6d; }
QPushButton#Action { background: #245e4e; border: 1px solid #367d68; color: white; font-weight: bold; }
QPushButton#Action:hover { background: #2d7963; }
QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox, QDateEdit { background: #171d20; border: 1px solid #354044; padding: 7px; selection-background-color: #347b68; }
QTableWidget { background: #151a1d; alternate-background-color: #1a2023; gridline-color: #30383b; border: 1px solid #30383b; }
QHeaderView::section { background: #20272a; color: #9fb0b2; padding: 7px; border: none; border-right: 1px solid #30383b; }
QTabWidget::pane { border: 1px solid #30383b; }
QMessageBox { background: #171b1e; }
"""

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("???")
        self.resize(1180, 760)
        central = QWidget()
        root = QHBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        sidebar = QFrame()
        sidebar.setObjectName("Sidebar")
        sidebar.setFixedWidth(205)
        side = QVBoxLayout(sidebar)
        side.setContentsMargins(14, 16, 14, 16)
        side.setSpacing(7)
        brand = QLabel("???")
        brand.setObjectName("Brand")
        side.addWidget(brand)
        side.addSpacing(20)

        self.stack = QStackedWidget()
        pages = [
            ("Обзор", DashboardPage()),
            ("Банковский счёт", AccountPage()),
            ("Биржа", StockMarketPage()),
            ("Портфель", PortfolioPage()),
            ("Вклады", DepositPage()),
            ("Моделирование", SimulationPage()),
            ("Отчёты", ReportsPage()),
        ]
        for index, (label, page) in enumerate(pages):
            button = QPushButton(label)
            button.setCheckable(True)
            button.setChecked(index == 0)
            button.clicked.connect(lambda checked=False, i=index: self.navigate(i))
            side.addWidget(button)
            self.stack.addWidget(page)
        side.addStretch()
        main = QVBoxLayout()
        main.setContentsMargins(22, 18, 22, 18)
        main.setSpacing(12)
        top = QHBoxLayout()
        title = QLabel("Обзор")
        title.setStyleSheet("font-size: 18px; font-weight: bold; color: #e6ecec;")
        top.addWidget(title)
        top.addStretch()
        main.addLayout(top)
        self.page_title = title
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setStyleSheet("color: #30383b;")
        main.addWidget(line)
        main.addWidget(self.stack)
        root.addWidget(sidebar)
        content = QWidget()
        content.setLayout(main)
        root.addWidget(content)
        self.setCentralWidget(central)
        self.nav_buttons = sidebar.findChildren(QPushButton)
        self.refresh_all()

    def navigate(self, index):
        self.stack.setCurrentIndex(index)
        self.page_title.setText(["Обзор", "Банковский счёт", "Биржа", "Портфель", "Вклады", "Моделирование", "Отчёты"][index])
        for i, button in enumerate(self.nav_buttons):
            button.setChecked(i == index)
        self.refresh_all()

    def refresh_all(self):
        page = self.stack.currentWidget()
        if hasattr(page, "refresh"):
            page.refresh()

def main():
    init_db()
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setStyleSheet(APP_STYLE)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
