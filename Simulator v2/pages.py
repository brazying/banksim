import random
from datetime import date
from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QTableWidget,
    QTableWidgetItem, QHeaderView, QLineEdit, QComboBox, QDoubleSpinBox, QSpinBox, QFormLayout,
    QMessageBox, QGroupBox)
from PyQt6.QtCore import Qt
from database import connect
from finance import to_cents, money, compound_interest, projected_value
from charts import CapitalChart, AllocationChart


TRANSACTION_LABELS = {
    "Income": "Доход",
    "Expense": "Расход",
    "Deposit": "Пополнение",
    "Withdrawal": "Снятие",
}

def heading(text, subtitle=""):
    box = QVBoxLayout() 
    title = QLabel(text)
    title.setStyleSheet("font-size: 19px; font-weight: bold;")
    box.addWidget(title)
    if subtitle:
        sub = QLabel(subtitle)
        sub.setStyleSheet("color: #8b999c;")
        box.addWidget(sub)
    return box


def metric(title, value):
    box = QGroupBox(title.upper())
    layout = QVBoxLayout(box)
    label = QLabel(value)
    label.setStyleSheet("font-size: 22px; font-weight: bold; color: #73e0bd; padding: 4px 0;")
    layout.addWidget(label)
    box.value_label = label
    return box


def configure_table(table):
    table.setAlternatingRowColors(True)
    table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
    table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
    table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
    table.verticalHeader().setVisible(False)

class DashboardPage(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.addLayout(heading("ОБЗОР", ""))
        row = QHBoxLayout()
        self.balance = metric("Баланс счёта", "0,00 ₽")
        self.portfolio = metric("Стоимость портфеля", "0,00 ₽")
        self.net = metric("Общий капитал", "0,00 ₽")
        for item in (self.balance, self.portfolio, self.net):
            row.addWidget(item)
        layout.addLayout(row)
        charts_row = QHBoxLayout()
        capital_box = QGroupBox("ИСТОРИЯ БАЛАНСА")
        capital_layout = QVBoxLayout(capital_box)
        self.capital_chart = CapitalChart()
        capital_layout.addWidget(self.capital_chart)
        allocation_box = QGroupBox("СТРУКТУРА АКТИВОВ")
        allocation_layout = QVBoxLayout(allocation_box)
        self.allocation_chart = AllocationChart()
        allocation_layout.addWidget(self.allocation_chart)
        charts_row.addWidget(capital_box, 2)
        charts_row.addWidget(allocation_box, 1)
        layout.addLayout(charts_row, 2)
        layout.addWidget(QLabel("ПОСЛЕДНИЕ ОПЕРАЦИИ"))
        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(["ДАТА", "ТИП", "КАТЕГОРИЯ", "ОПИСАНИЕ", "СУММА"])
        configure_table(self.table)
        layout.addWidget(self.table)

    def refresh(self):
        with connect() as conn:
            rows = conn.execute("SELECT * FROM transactions ORDER BY id DESC LIMIT 8").fetchall()
            income = conn.execute("SELECT COALESCE(SUM(amount_cents),0) FROM transactions WHERE tx_type IN ('Income','Deposit')").fetchone()[0]
            expense = conn.execute("SELECT COALESCE(SUM(amount_cents),0) FROM transactions WHERE tx_type IN ('Expense','Withdrawal')").fetchone()[0]
            assets = conn.execute("SELECT name, quantity, current_price_cents FROM assets UNION ALL SELECT s.name || ' (' || s.ticker || ')', h.quantity, s.price_cents FROM holdings h JOIN stocks s ON s.ticker=h.ticker WHERE h.quantity > 0").fetchall()
            trade_cash = conn.execute("SELECT COALESCE(SUM(CASE WHEN side='SELL' THEN total_cents ELSE -total_cents END),0) FROM trades").fetchone()[0]
            all_transactions = conn.execute("SELECT tx_date, tx_type, amount_cents FROM transactions ORDER BY tx_date, id").fetchall()
        balance = income - expense + trade_cash
        portfolio = sum(int(row["quantity"] * row["current_price_cents"]) for row in assets)
        self.balance.value_label.setText(money(balance))
        self.portfolio.value_label.setText(money(portfolio))
        self.net.value_label.setText(money(balance + portfolio))
        running = 0
        by_date = {}
        for tx in all_transactions:
            delta = tx["amount_cents"] if tx["tx_type"] in ("Income", "Deposit") else -tx["amount_cents"]
            running += delta
            by_date[tx["tx_date"]] = running
        labels = list(by_date.keys())[-30:]
        values = [by_date[key] / 100 for key in labels]
        self.capital_chart.plot_capital(labels, values)
        self.allocation_chart.plot_allocation(
            [row["name"] for row in assets],
            [row["quantity"] * row["current_price_cents"] / 100 for row in assets]
        )
        self.table.setRowCount(len(rows))
        for r, row in enumerate(rows):
            vals = [row["tx_date"], TRANSACTION_LABELS.get(row["tx_type"], row["tx_type"]), row["category"], row["description"], money(row["amount_cents"])]
            for c, value in enumerate(vals):
                self.table.setItem(r, c, QTableWidgetItem(str(value)))

class AccountPage(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.addLayout(heading("БАНКОВСКИЙ СЧЁТ", "Учёт доходов, расходов и движения денег"))
        self.balance_label = QLabel("Текущий баланс: —")
        self.balance_label.setStyleSheet("font-size: 18px; font-weight: bold; color: #73e0bd; padding: 4px 0;")
        layout.addWidget(self.balance_label)
        form_box = QGroupBox("НОВАЯ ОПЕРАЦИЯ")
        form = QFormLayout(form_box)
        self.kind = QComboBox()
        self.kind.addItem("Доход", "Income")
        self.kind.addItem("Расход", "Expense")
        self.kind.addItem("Пополнение", "Deposit")
        self.kind.addItem("Снятие", "Withdrawal")
        self.category = QLineEdit()
        self.category.setPlaceholderText("Например: зарплата, еда, перевод")
        self.description = QLineEdit()
        self.description.setPlaceholderText("Комментарий (необязательно)")
        self.amount = QDoubleSpinBox()
        self.amount.setRange(0.01, 1_000_000_000)
        self.amount.setDecimals(2)
        self.amount.setSuffix(" ₽")
        add = QPushButton("ДОБАВИТЬ ОПЕРАЦИЮ")
        add.setObjectName("Action")
        add.clicked.connect(self.add_transaction)
        form.addRow("ТИП", self.kind)
        form.addRow("КАТЕГОРИЯ", self.category)
        form.addRow("ОПИСАНИЕ", self.description)
        form.addRow("СУММА", self.amount)
        form.addRow("", add)
        layout.addWidget(form_box)
        layout.addWidget(QLabel("ИСТОРИЯ ОПЕРАЦИЙ"))
        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(["ДАТА", "ТИП", "КАТЕГОРИЯ", "ОПИСАНИЕ", "СУММА"])
        configure_table(self.table)
        layout.addWidget(self.table)

    def add_transaction(self):
        category = self.category.text().strip()
        if not category:
            QMessageBox.warning(self, "Не указана категория", "Укажи категорию операции.")
            return
        try:
            cents = to_cents(self.amount.value())
            with connect() as conn:
                conn.execute("INSERT INTO transactions(tx_date,tx_type,category,description,amount_cents) VALUES(?,?,?,?,?)",
                    (date.today().isoformat(), self.kind.currentData(), category, self.description.text().strip(), cents))
            self.category.clear()
            self.description.clear()
            self.amount.setValue(0.01)
            self.refresh()
            QMessageBox.information(self, "Сохранено", "Операция добавлена.")
        except Exception as exc:
            QMessageBox.critical(self, "Ошибка", str(exc))

    def refresh(self):
        with connect() as conn:
            rows = conn.execute("SELECT * FROM transactions ORDER BY id DESC").fetchall()
            income = conn.execute("SELECT COALESCE(SUM(amount_cents),0) FROM transactions WHERE tx_type IN ('Income','Deposit')").fetchone()[0]
            expense = conn.execute("SELECT COALESCE(SUM(amount_cents),0) FROM transactions WHERE tx_type IN ('Expense','Withdrawal')").fetchone()[0]
            trade_cash = conn.execute("SELECT COALESCE(SUM(CASE WHEN side='SELL' THEN total_cents ELSE -total_cents END),0) FROM trades").fetchone()[0]
        self.balance_label.setText(f"Текущий баланс: {money(income - expense + trade_cash)}")
        self.table.setRowCount(len(rows))
        for r, row in enumerate(rows):
            vals = [row["tx_date"], TRANSACTION_LABELS.get(row["tx_type"], row["tx_type"]), row["category"], row["description"], money(row["amount_cents"])]
            for c, value in enumerate(vals):
                self.table.setItem(r, c, QTableWidgetItem(str(value)))

class PortfolioPage(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.addLayout(heading("ПОРТФЕЛЬ", "Список активов и их стоимость"))
        box = QGroupBox("ДОБАВИТЬ / ОБНОВИТЬ АКТИВ")
        form = QFormLayout(box)
        self.name = QLineEdit()
        self.name.setPlaceholderText("Например: фонд")
        self.ticker = QLineEdit()
        self.ticker.setPlaceholderText("Например: FUND")
        self.quantity = QDoubleSpinBox()
        self.quantity.setRange(0.0001, 1_000_000_000)
        self.quantity.setDecimals(4)
        self.price = QDoubleSpinBox()
        self.price.setRange(0.01, 1_000_000_000)
        self.price.setDecimals(2)
        self.avg_price = QDoubleSpinBox()
        self.avg_price.setRange(0.01, 1_000_000_000)
        self.avg_price.setDecimals(2)
        for field in (self.price, self.avg_price):
            field.setSuffix(" ₽")
        add = QPushButton("СОХРАНИТЬ АКТИВ")
        add.setObjectName("Action")
        add.clicked.connect(self.save_asset)
        form.addRow("НАЗВАНИЕ", self.name)
        form.addRow("ТИКЕР", self.ticker)
        form.addRow("КОЛИЧЕСТВО", self.quantity)
        form.addRow("СРЕДНЯЯ ЦЕНА ПОКУПКИ", self.avg_price)
        form.addRow("ТЕКУЩАЯ ЦЕНА", self.price)
        form.addRow("", add)
        layout.addWidget(box)
        layout.addWidget(QLabel("АКТИВЫ В ПОРТФЕЛЕ"))
        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(["НАЗВАНИЕ", "ТИКЕР", "КОЛ-ВО", "СР. ПОКУПКА", "ТЕКУЩАЯ", "ПРИБЫЛЬ / УБЫТОК"])
        configure_table(self.table)
        layout.addWidget(self.table)

    def save_asset(self):
        name = self.name.text().strip()
        if not name:
            QMessageBox.warning(self, "Нет названия", "Укажи название актива.")
            return
        try:
            qty = self.quantity.value()
            avg = to_cents(self.avg_price.value())
            current = to_cents(self.price.value())
            with connect() as conn:
                conn.execute("""INSERT INTO assets(name,ticker,quantity,average_price_cents,current_price_cents)
                    VALUES(?,?,?,?,?) ON CONFLICT(name) DO UPDATE SET ticker=excluded.ticker, quantity=excluded.quantity,
                    average_price_cents=excluded.average_price_cents,current_price_cents=excluded.current_price_cents""",
                    (name, self.ticker.text().strip().upper(), qty, avg, current))
            self.name.clear()
            self.ticker.clear()
            self.refresh()
        except Exception as exc:
            QMessageBox.critical(self, "Ошибка", str(exc))

    def refresh(self):
        with connect() as conn:
            rows = conn.execute("SELECT * FROM assets ORDER BY name").fetchall()
        self.table.setRowCount(len(rows))
        for r, row in enumerate(rows):
            qty = row["quantity"]
            current_value = int(qty * row["current_price_cents"])
            cost_value = int(qty * row["average_price_cents"])
            pnl = current_value - cost_value
            vals = [row["name"], row["ticker"], f"{qty:g}", money(row["average_price_cents"]), money(row["current_price_cents"]), money(pnl)]
            for c, value in enumerate(vals):
                self.table.setItem(r, c, QTableWidgetItem(str(value)))

class DepositPage(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.addLayout(heading("КАЛЬКУЛЯТОР ВКЛАДА", "Сложные проценты / учебный расчёт"))
        box = QGroupBox("ПАРАМЕТРЫ")
        form = QFormLayout(box)
        self.principal = QDoubleSpinBox()
        self.principal.setRange(0.01, 1_000_000_000)
        self.principal.setDecimals(2)
        self.principal.setValue(10000)
        self.rate = QDoubleSpinBox()
        self.rate.setRange(0, 100)
        self.rate.setDecimals(2)
        self.rate.setValue(8)
        self.years = QDoubleSpinBox()
        self.years.setRange(0, 100)
        self.years.setDecimals(1)
        self.years.setValue(3)
        self.compounds = QComboBox()
        self.compounds.addItem("Ежегодно", 1)
        self.compounds.addItem("Ежеквартально", 4)
        self.compounds.addItem("Ежемесячно", 12)
        self.compounds.addItem("Ежедневно", 365)
        self.result = QLabel("—")
        self.result.setStyleSheet("font-size: 24px; color: #73e0bd; font-weight: bold;")
        self.interest = QLabel("")
        calc = QPushButton("РАССЧИТАТЬ")
        calc.setObjectName("Action")
        calc.clicked.connect(self.calculate)
        form.addRow("НАЧАЛЬНАЯ СУММА", self.principal)
        form.addRow("ГОДОВАЯ СТАВКА (%)", self.rate)
        form.addRow("СРОК (ЛЕТ)", self.years)
        form.addRow("КАПИТАЛИЗАЦИЯ", self.compounds)
        form.addRow("", calc)
        layout.addWidget(box)
        layout.addWidget(QLabel("ПРОГНОЗ БАЛАНСА"))
        layout.addWidget(self.result)
        layout.addWidget(self.interest)
        layout.addStretch()

    def calculate(self):
        try:
            principal = to_cents(self.principal.value())
            result = compound_interest(principal, self.rate.value(), self.years.value(), self.compounds.currentData())
            self.result.setText(money(result))
            self.interest.setText(f"Начисленные проценты: {money(result - principal)}")
            with connect() as conn:
                conn.execute("INSERT INTO deposit_scenarios(principal_cents,annual_rate,years,compounds_per_year,result_cents) VALUES(?,?,?,?,?)",
                    (principal, self.rate.value(), self.years.value(), self.compounds.currentData(), result))
        except Exception as exc:
            QMessageBox.warning(self, "Ошибка расчёта", str(exc))

class SimulationPage(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.addLayout(heading("МОДЕЛИРОВАНИЕ", "Прогноз при постоянной годовой доходности"))
        box = QGroupBox("СЦЕНАРИЙ")
        form = QFormLayout(box)
        self.initial = QDoubleSpinBox()
        self.initial.setRange(0.01, 1_000_000_000)
        self.initial.setDecimals(2)
        self.initial.setValue(10000)
        self.rate = QDoubleSpinBox()
        self.rate.setRange(-99, 100)
        self.rate.setDecimals(2)
        self.rate.setValue(6)
        self.years = QSpinBox()
        self.years.setRange(1, 50)
        self.years.setValue(10)
        self.output = QLabel("—")
        self.output.setStyleSheet("font-size: 24px; color: #73e0bd; font-weight: bold;")
        self.details = QLabel("Укажи параметры и рассчитай прогноз.")
        run = QPushButton("РАССЧИТАТЬ ПРОГНОЗ")
        run.setObjectName("Action")
        run.clicked.connect(self.run_projection)
        form.addRow("НАЧАЛЬНЫЙ КАПИТАЛ", self.initial)
        form.addRow("ГОДОВАЯ ДОХОДНОСТЬ (%)", self.rate)
        form.addRow("ЛЕТ", self.years)
        form.addRow("", run)
        layout.addWidget(box)
        layout.addWidget(QLabel("ПРОГНОЗИРУЕМАЯ СТОИМОСТЬ"))
        layout.addWidget(self.output)
        layout.addWidget(self.details)
        layout.addStretch()

    def run_projection(self):
        try:
            initial = to_cents(self.initial.value())
            result = projected_value(initial, self.rate.value(), self.years.value())
            self.output.setText(money(result))
            self.details.setText(f"Изменение: {money(result-initial)} • Постоянная доходность — допущение, а не предсказание.")
            with connect() as conn:
                conn.execute("INSERT INTO simulation_runs(initial_cents,annual_rate,years,final_cents) VALUES(?,?,?,?)",
                    (initial, self.rate.value(), self.years.value(), result))
        except Exception as exc:
            QMessageBox.warning(self, "Ошибка моделирования", str(exc))

class ReportsPage(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.addLayout(heading("ОТЧЁТЫ", "Сводка по сохранённым данным"))
        self.summary = QLabel("")
        self.summary.setStyleSheet("font-size: 14px; line-height: 1.5;")
        layout.addWidget(self.summary)
        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["ТИП", "КОЛИЧЕСТВО", "ИТОГО"])
        configure_table(self.table)
        layout.addWidget(self.table)
        layout.addStretch()

    def refresh(self):
        with connect() as conn:
            rows = conn.execute("""SELECT tx_type, COUNT(*) AS n, SUM(amount_cents) AS total
                FROM transactions GROUP BY tx_type ORDER BY tx_type""").fetchall()
            income = conn.execute("SELECT COALESCE(SUM(amount_cents),0) FROM transactions WHERE tx_type='Income'").fetchone()[0]
            expense = conn.execute("SELECT COALESCE(SUM(amount_cents),0) FROM transactions WHERE tx_type='Expense'").fetchone()[0]
        self.summary.setText(f"Доходы: {money(income)}     Расходы: {money(expense)}     Чистый поток: {money(income-expense)}")
        self.table.setRowCount(len(rows))
        for r, row in enumerate(rows):
            vals = [TRANSACTION_LABELS.get(row["tx_type"], row["tx_type"]), row["n"], money(row["total"] or 0)]
            for c, value in enumerate(vals):
                self.table.setItem(r, c, QTableWidgetItem(str(value)))


class StockMarketPage(QWidget):
    """Локальный симулируемый рынок: котировки случайно меняются, сделки меняют денежный баланс."""
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.addLayout(heading("РЫНОК АКЦИЙ", "Учебная биржа: котировки меняются автоматически, реальные деньги не используются"))
        summary = QHBoxLayout()
        self.cash_label = QLabel("Доступно: —")
        self.cash_label.setStyleSheet("font-size: 16px; font-weight: bold; color: #73e0bd;")
        self.portfolio_label = QLabel("Стоимость акций: —")
        self.portfolio_label.setStyleSheet("font-size: 16px; font-weight: bold;")
        summary.addWidget(self.cash_label)
        summary.addStretch()
        summary.addWidget(self.portfolio_label)
        layout.addLayout(summary)

        market_box = QGroupBox("КОТИРОВКИ")
        market_layout = QVBoxLayout(market_box)
        self.market = QTableWidget(0, 5)
        self.market.setHorizontalHeaderLabels(["ТИКЕР", "КОМПАНИЯ", "ЦЕНА", "ИЗМЕНЕНИЕ", "ИЗМЕНЕНИЕ, %"])
        configure_table(self.market)
        self.market.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.market.itemSelectionChanged.connect(self.update_selected_price)
        market_layout.addWidget(self.market)
        layout.addWidget(market_box, 3)

        trade_box = QGroupBox("СОВЕРШИТЬ СДЕЛКУ")
        trade_form = QHBoxLayout(trade_box)
        self.selected_stock = QLabel("Выбери акцию в таблице выше")
        self.selected_stock.setMinimumWidth(170)
        self.quantity = QDoubleSpinBox()
        self.quantity.setRange(0.01, 1_000_000)
        self.quantity.setDecimals(2)
        self.quantity.setSingleStep(1.0)
        self.quantity.setValue(1.0)
        buy = QPushButton("КУПИТЬ")
        buy.setObjectName("Action")
        sell = QPushButton("ПРОДАТЬ")
        sell.setObjectName("Action")
        buy.clicked.connect(lambda: self.execute_trade("BUY"))
        sell.clicked.connect(lambda: self.execute_trade("SELL"))
        trade_form.addWidget(self.selected_stock, 2)
        trade_form.addWidget(QLabel("Количество:"))
        trade_form.addWidget(self.quantity)
        trade_form.addWidget(buy)
        trade_form.addWidget(sell)
        layout.addWidget(trade_box)

        layout.addWidget(QLabel("МОИ АКЦИИ"))
        self.holdings_table = QTableWidget(0, 5)
        self.holdings_table.setHorizontalHeaderLabels(["ТИКЕР", "КОМПАНИЯ", "КОЛИЧЕСТВО", "СРЕДНЯЯ ПОКУПКА", "ТЕКУЩАЯ СТОИМОСТЬ"])
        configure_table(self.holdings_table)
        layout.addWidget(self.holdings_table, 2)

        self.timer = QTimer(self)
        self.timer.setInterval(15000)
        self.timer.timeout.connect(self.move_market)
        self.timer.start()
        self.selected_ticker = None

    def cash_balance(self, conn):
        tx_in = conn.execute("SELECT COALESCE(SUM(amount_cents),0) FROM transactions WHERE tx_type IN ('Income','Deposit')").fetchone()[0]
        tx_out = conn.execute("SELECT COALESCE(SUM(amount_cents),0) FROM transactions WHERE tx_type IN ('Expense','Withdrawal')").fetchone()[0]
        trades = conn.execute("SELECT COALESCE(SUM(CASE WHEN side='SELL' THEN total_cents ELSE -total_cents END),0) FROM trades").fetchone()[0]
        return tx_in - tx_out + trades

    def refresh(self):
        with connect() as conn:
            stocks = conn.execute("SELECT * FROM stocks ORDER BY ticker").fetchall()
            cash = self.cash_balance(conn)
            holdings = conn.execute("SELECT h.*, s.name, s.price_cents FROM holdings h JOIN stocks s ON s.ticker=h.ticker WHERE h.quantity > 0 ORDER BY h.ticker").fetchall()
        self.cash_label.setText(f"Доступно: {money(cash)}")
        self.portfolio_label.setText(f"Стоимость акций: {money(sum(int(h['quantity'] * h['price_cents']) for h in holdings))}")
        selected = self.selected_ticker
        self.market.setRowCount(len(stocks))
        for r, stock in enumerate(stocks):
            change = stock["price_cents"] - stock["previous_price_cents"]
            pct = change / stock["previous_price_cents"] * 100
            vals = [stock["ticker"], stock["name"], money(stock["price_cents"]), money(change), f"{pct:+.2f}%"]
            for c, value in enumerate(vals):
                item = QTableWidgetItem(str(value))
                if c >= 3:
                    item.setForeground(Qt.GlobalColor.green if change >= 0 else Qt.GlobalColor.red)
                self.market.setItem(r, c, item)
            if stock["ticker"] == selected:
                self.market.selectRow(r)
        self.holdings_table.setRowCount(len(holdings))
        for r, h in enumerate(holdings):
            vals = [h["ticker"], h["name"], f"{h['quantity']:.2f}", money(h["average_price_cents"]), money(int(h["quantity"] * h["price_cents"]))]
            for c, value in enumerate(vals):
                self.holdings_table.setItem(r, c, QTableWidgetItem(str(value)))
        self.update_selected_price()

    def update_selected_price(self):
        row = self.market.currentRow()
        if row < 0:
            self.selected_stock.setText("Выбери акцию в таблице выше")
            return
        item = self.market.item(row, 0)
        if item:
            self.selected_ticker = item.text()
            self.selected_stock.setText(f"Выбрано: {self.selected_ticker}")

    def move_market(self):
        with connect() as conn:
            rows = conn.execute("SELECT ticker, price_cents, volatility FROM stocks").fetchall()
            for stock in rows:
                # Малые случайные колебания с ограничением одного шага примерно в +/- 3%.
                pct = max(-0.03, min(0.03, random.gauss(0, stock["volatility"])))
                new_price = max(100, int(round(stock["price_cents"] * (1 + pct))))
                conn.execute("UPDATE stocks SET previous_price_cents=price_cents, price_cents=?, updated_at=CURRENT_TIMESTAMP WHERE ticker=?",
                             (new_price, stock["ticker"]))
        self.refresh()

    def execute_trade(self, side):
        ticker = self.selected_ticker
        if not ticker:
            QMessageBox.warning(self, "Акция не выбрана", "Сначала выбери акцию в таблице котировок.")
            return
        quantity = round(self.quantity.value(), 2)
        try:
            with connect() as conn:
                stock = conn.execute("SELECT * FROM stocks WHERE ticker=?", (ticker,)).fetchone()
                if not stock:
                    raise ValueError("Акция не найдена.")
                price = stock["price_cents"]
                total = int(round(price * quantity))
                cash = self.cash_balance(conn)
                holding = conn.execute("SELECT quantity, average_price_cents FROM holdings WHERE ticker=?", (ticker,)).fetchone()
                held = holding["quantity"] if holding else 0.0
                if side == "BUY":
                    if cash < total:
                        raise ValueError(f"Недостаточно денег. Доступно: {money(cash)}, нужно: {money(total)}.")
                    old_qty = held
                    new_qty = round(old_qty + quantity, 4)
                    old_cost = old_qty * (holding["average_price_cents"] if holding else 0)
                    avg = int(round((old_cost + quantity * price) / new_qty)) if new_qty else 0
                    conn.execute("INSERT INTO holdings(ticker,quantity,average_price_cents) VALUES(?,?,?) ON CONFLICT(ticker) DO UPDATE SET quantity=excluded.quantity, average_price_cents=excluded.average_price_cents",
                                 (ticker, new_qty, avg))
                else:
                    if held + 1e-9 < quantity:
                        raise ValueError(f"Недостаточно акций для продажи. У тебя: {held:.2f} шт.")
                    new_qty = round(held - quantity, 4)
                    conn.execute("UPDATE holdings SET quantity=?, average_price_cents=CASE WHEN ?=0 THEN 0 ELSE average_price_cents END WHERE ticker=?",
                                 (new_qty, new_qty, ticker))
                conn.execute("INSERT INTO trades(trade_date,ticker,side,quantity,price_cents,total_cents) VALUES(?,?,?,?,?,?)",
                             (date.today().isoformat(), ticker, side, quantity, price, total))
            action = "Куплено" if side == "BUY" else "Продано"
            QMessageBox.information(self, "Сделка выполнена", f"{action} {quantity:.2f} акций {ticker} по {money(price)} за штуку.\nСумма: {money(total)}.")
            self.refresh()
        except Exception as exc:
            QMessageBox.warning(self, "Не удалось совершить сделку", str(exc))
