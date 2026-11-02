import sys
from PyQt6.QtWidgets import QApplication, QMainWindow, QWidget, QHBoxLayout, QVBoxLayout, QPushButton, QLabel, QStackedWidget, QFrame
from PyQt6.QtCore import Qt
from database import init_db
from pages import DashboardPage, AccountPage, PortfolioPage, DepositPage, SimulationPage, ReportsPage, StockMarketPage
from theme import STYLE

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("LEDGER — финансовый симулятор")
        self.resize(1240, 800)
        central = QWidget()
        central.setObjectName("Root")
        root = QHBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        sidebar = QFrame()
        sidebar.setObjectName("Sidebar")
        sidebar.setFixedWidth(210)
        side = QVBoxLayout(sidebar)
        side.setContentsMargins(0, 22, 0, 18)
        side.setSpacing(0)

        brand = QLabel("Ledger")
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
        self.nav_buttons = []
        for index, (label, page) in enumerate(pages):
            button = QPushButton(label)
            button.setObjectName("Nav")
            button.setCheckable(True)
            button.setChecked(index == 0)
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            button.clicked.connect(lambda checked=False, i=index: self.navigate(i))
            side.addWidget(button)
            self.nav_buttons.append(button)
            self.stack.addWidget(page)
        side.addStretch()

        content = QWidget()
        main = QVBoxLayout(content)
        main.setContentsMargins(30, 26, 30, 22)
        main.addWidget(self.stack)
        root.addWidget(sidebar)
        root.addWidget(content, 1)
        self.setCentralWidget(central)
        self.refresh_all()

    def navigate(self, index):
        self.stack.setCurrentIndex(index)
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
    app.setStyleSheet(STYLE)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
