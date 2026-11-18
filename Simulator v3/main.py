import sys
from PyQt6.QtWidgets import QApplication, QMainWindow, QWidget, QHBoxLayout, QVBoxLayout, QPushButton, QLabel, QStackedWidget, QFrame
from PyQt6.QtCore import Qt, QTimer
from database import init_db
from pages import DashboardPage, AccountPage, PortfolioPage, DepositPage, SimulationPage, ReportsPage, StockMarketPage, BondsPage
from theme import STYLE

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("bankSim — финансовый симулятор")
        self.resize(1360, 860)
        self.setMinimumSize(1040, 700)
        central = QWidget()
        central.setObjectName("Root")
        root = QHBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        sidebar = QFrame()
        sidebar.setObjectName("Sidebar")
        sidebar.setFixedWidth(224)
        side = QVBoxLayout(sidebar)
        side.setContentsMargins(0, 24, 0, 18)
        side.setSpacing(2)

        brand = QLabel("bankSim")
        brand.setObjectName("Brand")
        side.addWidget(brand)
        brand_caption = QLabel("PERSONAL FINANCE SIMULATOR")
        brand_caption.setObjectName("BrandCaption")
        side.addWidget(brand_caption)
        side.addSpacing(28)

        self.stack = QStackedWidget()
        self.stock_market_page = StockMarketPage()
        self.bonds_page = BondsPage()
        pages = [
            ("Обзор", DashboardPage()),
            ("Банковский счёт", AccountPage()),
            ("Биржа", self.stock_market_page),
            ("Облигации", self.bonds_page),
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
            button.setToolTip(f"Открыть раздел «{label}»")
            button.clicked.connect(lambda checked=False, i=index: self.navigate(i))
            side.addWidget(button)
            self.nav_buttons.append(button)
            self.stack.addWidget(page)
        side.addStretch()
        side_footer = QLabel("Учебный финансовый симулятор")
        side_footer.setObjectName("Muted")
        side_footer.setWordWrap(True)
        side_footer.setContentsMargins(18, 0, 12, 0)
        side.addWidget(side_footer)

        content = QWidget()
        main = QVBoxLayout(content)
        main.setContentsMargins(28, 24, 28, 22)
        main.addWidget(self.stack)
        root.addWidget(sidebar)
        root.addWidget(content, 1)
        self.setCentralWidget(central)
        self.refresh_all()
        # Единственный таймер рынка: 15 секунд реального времени = 1 час симуляции.
        self.market_timer = QTimer(self)
        self.market_timer.setInterval(15000)
        self.market_timer.timeout.connect(self.advance_market_hour)
        self.market_timer.start()

    def advance_market_hour(self):
        self.stock_market_page.move_market()
        self.bonds_page.move_bond_market()
        # Страницы, не являющиеся рынками, тоже должны показывать актуальные
        # деньги и стоимость портфеля после купонов, погашений и переоценки.
        current = self.stack.currentWidget()
        if isinstance(current, SimulationPage):
            current.refresh_live_values()
        elif current not in (self.stock_market_page, self.bonds_page) and hasattr(current, "refresh"):
            current.refresh()

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
