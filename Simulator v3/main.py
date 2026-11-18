import sys
from PyQt6.QtWidgets import QApplication, QMainWindow, QWidget, QHBoxLayout, QVBoxLayout, QPushButton, QLabel, QStackedWidget, QFrame, QScrollArea, QTabWidget
from PyQt6.QtCore import Qt, QTimer
from database import init_db
from pages import DashboardPage, AccountPage, PortfolioPage, DepositPage, SimulationPage, ReportsPage, StockMarketPage, BondsPage
from theme import STYLE

from theme import STYLE, BG, SURFACE, LINE, TEXT, MUTED, ACCENT

class ExchangePage(QWidget):
    def __init__(self, stocks_page, bonds_page):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        header = QVBoxLayout()
        header.setSpacing(2)
        title = QLabel("Биржа")
        title.setObjectName("PageTitle")
        subtitle = QLabel("Акции и облигации в одном разделе")
        subtitle.setObjectName("PageSub")
        header.addWidget(title)
        header.addWidget(subtitle)
        layout.addLayout(header)

        self.tabs = QTabWidget()
        self.tabs.setDocumentMode(True)
        self.tabs.setUsesScrollButtons(False)
        self.tabs.setObjectName("ExchangeTabs")
        self.stocks_page = stocks_page
        self.bonds_page = bonds_page
        self.tabs.addTab(self._scroll_page(stocks_page), "Акции")
        self.tabs.addTab(self._scroll_page(bonds_page), "Облигации")
        self.tabs.currentChanged.connect(self.refresh_current)
        layout.addWidget(self.tabs, 1)

    def _scroll_page(self, page):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet(
            f"QScrollArea {{ background: {BG}; border: none; }}"
            f"QScrollArea > QWidget > QWidget {{ background: {BG}; }}"
        )
        scroll.viewport().setAutoFillBackground(False)
        scroll.viewport().setStyleSheet(f"background: {BG};")
        page.setAutoFillBackground(False)
        page.setStyleSheet(f"background: {BG};")
        scroll.setWidget(page)
        page.setAutoFillBackground(False)
        return scroll

    def current_page(self):
        scroll = self.tabs.currentWidget()
        return scroll.widget() if isinstance(scroll, QScrollArea) else scroll

    def refresh_current(self):
        page = self.current_page()
        if hasattr(page, "refresh"):
            page.refresh()

    def refresh(self):
        self.refresh_current()

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
        side.addSpacing(28)

        self.stack = QStackedWidget()
        self.stock_market_page = StockMarketPage()
        self.bonds_page = BondsPage()
        self.exchange_page = ExchangePage(self.stock_market_page, self.bonds_page)
        pages = [
            ("Обзор", DashboardPage()),
            ("Банковский счёт", AccountPage()),
            ("Биржа", self.exchange_page),
            ("Портфель", PortfolioPage()),
            ("Вклады", DepositPage()),
            ("Моделирование", SimulationPage()),
            ("Отчёты", ReportsPage()),
        ]
        self.nav_buttons = []
        self.page_widgets = []
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
            self.page_widgets.append(page)
            if label == "Отчёты":
                self.stack.addWidget(page)
            else:
                page_scroll = QScrollArea()
                page_scroll.setWidgetResizable(True)
                page_scroll.setFrameShape(QFrame.Shape.NoFrame)
                page_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
                page_scroll.setStyleSheet(
                    f"QScrollArea {{ background: {BG}; border: none; }}"
                    f"QAbstractScrollArea#qt_scrollarea_viewport {{ background: {BG}; }}"
                )
                page_scroll.viewport().setAutoFillBackground(False)
                page_scroll.viewport().setStyleSheet(f"background: {BG};")
                page_scroll.setWidget(page)
                page.setAutoFillBackground(False)
                page.setStyleSheet(f"background: {BG};")
                self.stack.addWidget(page_scroll)
        side.addStretch()

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
        current = self.current_page()
        if isinstance(current, SimulationPage):
            current.refresh_live_values()
        elif current is self.exchange_page:
            self.exchange_page.refresh()
        elif current not in (self.stock_market_page, self.bonds_page) and hasattr(current, "refresh"):
            current.refresh()

    def navigate(self, index):
        self.stack.setCurrentIndex(index)
        for i, button in enumerate(self.nav_buttons):
            button.setChecked(i == index)
        self.refresh_all()

    def refresh_all(self):
        page = self.current_page()
        if hasattr(page, "refresh"):
            page.refresh()

    def current_page(self):
        current = self.stack.currentWidget()
        if isinstance(current, QScrollArea):
            return current.widget()
        return current

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
