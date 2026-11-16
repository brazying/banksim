from datetime import date, timedelta
from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QTableWidget,
    QTableWidgetItem, QHeaderView, QLineEdit, QComboBox, QDoubleSpinBox, QSpinBox, QFormLayout,
    QMessageBox, QGroupBox, QFrame, QScrollArea)
from PyQt6.QtCore import Qt
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
from database import connect, record_financial_snapshot
from finance import to_cents, money, compound_interest, projected_value, monte_carlo, monte_carlo_price_step, monte_carlo_capital
from charts import CapitalChart, AllocationChart, style_axes
from theme import *
from PyQt6.QtGui import QColor, QFont


TRANSACTION_LABELS = {
    "Income": "Доход",
    "Expense": "Расход",
    "Deposit": "Пополнение",
    "Withdrawal": "Снятие",
}

NUMERIC = {"Сумма", "Цена", "Изменение", "Изменение, %", "Итого", "Количество", "Кол-во",
           "Средняя покупка", "Ср. покупка", "Текущая", "Текущая стоимость", "Прибыль / убыток", "Прибыль / убыток, %"}
RIGHT = Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
LEFT = Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter

def heading(text, subtitle=""):
    box = QVBoxLayout()
    box.setSpacing(2)
    box.setContentsMargins(0, 0, 0, 10)
    title = QLabel(text)
    title.setObjectName("PageTitle")
    box.addWidget(title)
    return box

def section(text):
    label = QLabel(text)
    label.setObjectName("Section")
    return label

def metric(title, value, hero=False):
    box = QFrame()
    box.setObjectName("Hero" if hero else "Metric")
    lay = QVBoxLayout(box)
    lay.setContentsMargins(20, 16, 20, 16)
    lay.setSpacing(2)
    t = QLabel(title)
    t.setObjectName("MetricTitle")
    label = QLabel(value)
    label.setObjectName("MetricValue")
    lay.addWidget(t)
    lay.addWidget(label)
    box.value_label = label
    return box

def configure_table(table):
    table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
    table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
    table.setShowGrid(False)
    table.setFocusPolicy(Qt.FocusPolicy.NoFocus)
    table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
    table.horizontalHeader().setDefaultAlignment(LEFT)
    table.verticalHeader().setVisible(False)
    table.verticalHeader().setDefaultSectionSize(40)
    for c in range(table.columnCount()):
        h = table.horizontalHeaderItem(c)
        if h and h.text() in NUMERIC:
            h.setTextAlignment(RIGHT)

def wrap(table):
    card = QFrame()
    card.setObjectName("Card")
    lay = QVBoxLayout(card)
    lay.setContentsMargins(6, 6, 6, 6)
    lay.addWidget(table)
    return card

def put(table, r, c, value, color=None, bold=False):
    text = str(value)
    item = QTableWidgetItem(text)
    if color is None:
        if text.startswith("+"):
            color = UP
        elif text.startswith(("-", "−")):
            color = DOWN
    if color:
        item.setForeground(QColor(color))
    if bold:
        f = item.font()
        f.setBold(True)
        item.setFont(f)
    h = table.horizontalHeaderItem(c)
    numeric = bool(h and h.text() in NUMERIC)
    if numeric:
        mono = QFont("Helvetica", 10)
        mono.setBold(item.font().bold())
        item.setFont(mono)
    item.setTextAlignment(RIGHT if numeric else LEFT)
    table.setItem(r, c, item)

def signed(row):
    plus = row["tx_type"] in ("Income", "Deposit")
    return ("+" if plus else "−") + money(row["amount_cents"])

def cash_balance(conn):
    """Единый денежный баланс: операции по счёту с учётом покупок и продаж акций."""
    income = conn.execute(
        "SELECT COALESCE(SUM(amount_cents),0) FROM transactions WHERE tx_type IN ('Income','Deposit')"
    ).fetchone()[0]
    expense = conn.execute(
        "SELECT COALESCE(SUM(amount_cents),0) FROM transactions WHERE tx_type IN ('Expense','Withdrawal')"
    ).fetchone()[0]
    trade_cash = conn.execute(
        "SELECT COALESCE(SUM(CASE WHEN side='SELL' THEN total_cents ELSE -total_cents END),0) FROM trades"
    ).fetchone()[0]
    bond_trade_cash = conn.execute(
        "SELECT COALESCE(SUM(CASE WHEN side='SELL' THEN total_cents ELSE -total_cents END),0) FROM bond_trades"
    ).fetchone()[0]
    coupons = conn.execute("SELECT COALESCE(SUM(amount_cents),0) FROM bond_coupon_payments").fetchone()[0]
    return income - expense + trade_cash + bond_trade_cash + coupons


def operation_rows(conn):
    rows = []
    transactions = conn.execute("SELECT * FROM transactions").fetchall()
    trades = conn.execute("SELECT * FROM trades").fetchall()
    bond_trades = conn.execute("SELECT * FROM bond_trades").fetchall()
    coupons = conn.execute("SELECT * FROM bond_coupon_payments").fetchall()

    for row in transactions:
        plus = row["tx_type"] in ("Income", "Deposit")
        rows.append({
            "date": row["tx_date"], "id": row["id"], "source": 0,
            "type": TRANSACTION_LABELS.get(row["tx_type"], row["tx_type"]),
            "category": row["category"], "description": row["description"],
            "amount": ("+" if plus else "−") + money(row["amount_cents"]),
            "delta": row["amount_cents"] if plus else -row["amount_cents"],
        })

    for row in trades:
        is_sale = row["side"] == "SELL"
        action = "Продажа акций" if is_sale else "Покупка акций"
        rows.append({
            "date": row["trade_date"], "id": row["id"], "source": 1,
            "type": action, "category": "Биржа",
            "description": f"{row['ticker']} · {row['quantity']:.2f} шт. по {money(row['price_cents'])}",
            "amount": ("+" if is_sale else "−") + money(row["total_cents"]),
            "delta": row["total_cents"] if is_sale else -row["total_cents"],
        })

    for row in bond_trades:
        is_sale = row["side"] == "SELL"
        rows.append({
            "date": row["trade_date"], "id": row["id"], "source": 2,
            "type": "Продажа облигаций" if is_sale else "Покупка облигаций",
            "category": "Облигации",
            "description": f"{row['ticker']} · {row['quantity']:.2f} шт. по {money(row['price_cents'])}",
            "amount": ("+" if is_sale else "−") + money(row["total_cents"]),
            "delta": row["total_cents"] if is_sale else -row["total_cents"],
        })
    for row in coupons:
        rows.append({
            "date": row["payment_date"], "id": row["id"], "source": 3,
            "type": "Выплата купона", "category": "Купонный доход",
            "description": row["ticker"] + " · полугодовая выплата",
            "amount": "+" + money(row["amount_cents"]), "delta": row["amount_cents"],
        })
    rows.sort(key=lambda item: (item["date"], item["id"], item["source"]), reverse=True)
    return rows


class DashboardPage(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.addLayout(heading("Обзор", ""))
        row = QHBoxLayout()
        self.balance = metric("Баланс счёта", "0,00 ₽")
        self.portfolio = metric("Стоимость портфеля", "0,00 ₽")
        self.net = metric("Общий капитал", "0,00 ₽", hero=True)
        row.setSpacing(12)
        for item in (self.balance, self.portfolio, self.net):
            row.addWidget(item, 1)
        layout.addLayout(row)
        charts_row = QHBoxLayout()
        charts_row.setSpacing(12)
        capital_box = QGroupBox("История баланса")
        capital_layout = QVBoxLayout(capital_box)
        self.capital_chart = CapitalChart()
        capital_layout.addWidget(self.capital_chart)
        allocation_box = QGroupBox("Структура активов")
        allocation_layout = QVBoxLayout(allocation_box)
        self.allocation_chart = AllocationChart()
        allocation_layout.addWidget(self.allocation_chart)
        charts_row.addWidget(capital_box, 2)
        charts_row.addWidget(allocation_box, 1)
        layout.addLayout(charts_row, 2)
        layout.addWidget(section("Последние операции"))
        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(["Дата", "Тип", "Категория", "Описание", "Сумма"])
        configure_table(self.table)
        layout.addWidget(wrap(self.table))

    def refresh(self):
        with connect() as conn:
            rows = operation_rows(conn)[:8]
            balance = cash_balance(conn)
            assets = conn.execute("""
                SELECT a.name AS name, a.quantity AS quantity,
                       a.current_price_cents AS current_price_cents
                FROM assets a
                WHERE NOT EXISTS (
                    SELECT 1 FROM holdings h
                    WHERE h.ticker = UPPER(a.ticker) AND h.quantity > 0
                )
                UNION ALL
                SELECT s.name || ' (' || s.ticker || ')' AS name,
                       h.quantity AS quantity,
                       s.price_cents AS current_price_cents
                FROM holdings h JOIN stocks s ON s.ticker = h.ticker
                WHERE h.quantity > 0
            """).fetchall()
            all_operations = operation_rows(conn)
        portfolio = sum(int(row["quantity"] * row["current_price_cents"]) for row in assets)
        self.balance.value_label.setText(money(balance))
        self.portfolio.value_label.setText(money(portfolio))
        self.net.value_label.setText(money(balance + portfolio))
        running = 0
        by_date = {}
        for operation in reversed(all_operations):
            running += operation["delta"]
            by_date[operation["date"]] = running
        labels = list(by_date.keys())[-30:]
        values = [by_date[key] / 100 for key in labels]
        self.capital_chart.plot_capital(labels, values)
        self.allocation_chart.plot_allocation(
            [row["name"] for row in assets],
            [row["quantity"] * row["current_price_cents"] / 100 for row in assets]
        )
        self.table.setRowCount(len(rows))
        for r, row in enumerate(rows):
            vals = [row["date"], row["type"], row["category"], row["description"], row["amount"]]
            for c, value in enumerate(vals):
                put(self.table, r, c, value)

class AccountPage(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.addLayout(heading("Банковский счёт", ""))
        self.balance_label = QLabel("Текущий баланс: —")
        self.balance_label.setStyleSheet("font-size: 18px; font-weight: bold; color: #dde0e4; font-family: Helvetica, Arial, sans-serif; padding: 4px 0;")
        layout.addWidget(self.balance_label)
        form_box = QGroupBox("Новая операция")
        form = QFormLayout(form_box)
        self.kind = QComboBox()
        self.kind.addItem("Доход", "Income")
        self.kind.addItem("Расход", "Expense")
        self.kind.addItem("Пополнение", "Deposit")
        self.kind.addItem("Снятие", "Withdrawal")
        self.category = QLineEdit()
        self.description = QLineEdit()
        self.amount = QDoubleSpinBox()
        self.amount.setRange(0.01, 1_000_000_000)
        self.amount.setDecimals(2)
        self.amount.setSuffix(" ₽")
        add = QPushButton("Добавить операцию")
        add.setObjectName("Action")
        add.clicked.connect(self.add_transaction)
        form.addRow("Тип", self.kind)
        form.addRow("Категория", self.category)
        form.addRow("Описание", self.description)
        form.addRow("Сумма", self.amount)
        form.addRow("", add)
        layout.addWidget(form_box)
        layout.addWidget(section("История операций"))
        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(["Дата", "Тип", "Категория", "Описание", "Сумма"])
        configure_table(self.table)
        layout.addWidget(wrap(self.table))

    def add_transaction(self):
        category = self.category.text().strip()
        if not category:
            QMessageBox.warning(self, "Не указана категория", "Укажи категорию операции.")
            return
        try:
            cents = to_cents(self.amount.value())
            tx_type = self.kind.currentData()
            with connect() as conn:
                if tx_type in ("Expense", "Withdrawal"):
                    available = cash_balance(conn)
                    if available < cents:
                        shortfall = cents - available
                        QMessageBox.warning(
                            self, "Недостаточно средств",
                            f"Доступный баланс: {money(available)}\n"
                            f"Сумма операции: {money(cents)}\n"
                            f"Не хватает: {money(shortfall)}.\n"
                            "Операция не добавлена. Сначала пополни счёт."
                        )
                        return
                conn.execute("INSERT INTO transactions(tx_date,tx_type,category,description,amount_cents) VALUES(?,?,?,?,?)",
                    (date.today().isoformat(), tx_type, category, self.description.text().strip(), cents))
                record_financial_snapshot(conn)
            self.category.clear()
            self.description.clear()
            self.amount.setValue(0.01)
            self.refresh()
            QMessageBox.information(self, "Сохранено", "Операция добавлена.")
        except Exception as exc:
            QMessageBox.critical(self, "Ошибка", str(exc))

    def refresh(self):
        with connect() as conn:
            rows = operation_rows(conn)
            balance = cash_balance(conn)
        self.balance_label.setText(f"Текущий баланс: {money(balance)}")
        self.table.setRowCount(len(rows))
        for r, row in enumerate(rows):
            vals = [row["date"], row["type"], row["category"], row["description"], row["amount"]]
            for c, value in enumerate(vals):
                put(self.table, r, c, value)

class PortfolioPage(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.addLayout(heading("Портфель", ""))
        box = QGroupBox("Добавить / обновить актив")
        form = QFormLayout(box)
        self.name = QLineEdit()
        self.ticker = QLineEdit()
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
        add = QPushButton("Сохранить актив")
        add.setObjectName("Action")
        add.clicked.connect(self.save_asset)
        form.addRow("Название", self.name)
        form.addRow("Тикер", self.ticker)
        form.addRow("Количество", self.quantity)
        form.addRow("Средняя цена покупки", self.avg_price)
        form.addRow("Текущая цена", self.price)
        form.addRow("", add)
        layout.addWidget(box)
        layout.addWidget(section("Активы в портфеле"))
        self.table = QTableWidget(0, 7)
        self.table.setHorizontalHeaderLabels(["Название", "Тикер", "Кол-во", "Ср. покупка", "Текущая", "Прибыль / убыток", "Прибыль / убыток, %"])
        configure_table(self.table)
        layout.addWidget(wrap(self.table))

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
                record_financial_snapshot(conn)
            self.name.clear()
            self.ticker.clear()
            self.refresh()
        except Exception as exc:
            QMessageBox.critical(self, "Ошибка", str(exc))

    def refresh(self):
        with connect() as conn:
            manual = conn.execute("SELECT * FROM assets ORDER BY name").fetchall()
            market = conn.execute("""
                SELECT s.name, h.ticker, h.quantity, h.average_price_cents, s.price_cents
                FROM holdings h JOIN stocks s ON s.ticker=h.ticker
                WHERE h.quantity > 0 ORDER BY h.ticker
            """).fetchall()

        # Биржевые позиции являются основным источником для тикеров,
        # уже купленных через рынок; не дублируем их ручными активами.
        market_tickers = {row["ticker"].upper() for row in market}
        rows = [
            (row["name"], row["ticker"], row["quantity"], row["average_price_cents"],
             row["current_price_cents"])
            for row in manual
            if not row["ticker"] or row["ticker"].upper() not in market_tickers
        ]
        rows.extend(
            (row["name"], row["ticker"], row["quantity"], row["average_price_cents"], row["price_cents"])
            for row in market
        )

        self.table.setRowCount(len(rows))
        for r, row in enumerate(rows):
            name, ticker, qty, avg_price, current_price = row
            current_value = int(qty * current_price)
            cost_value = int(qty * avg_price)
            pnl = current_value - cost_value
            pnl_pct = (pnl / cost_value * 100) if cost_value else 0.0
            vals = [name, ticker, f"{qty:g}", money(avg_price), money(current_price),
                    ("+" if pnl > 0 else "") + money(pnl), f"{pnl_pct:+.2f}%"]
            for c, value in enumerate(vals):
                put(self.table, r, c, value)


class BondsPage(QWidget):
    """Учебный рынок облигаций с плавающей рыночной ценой и полугодовыми купонами."""
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.addLayout(heading("Рынок облигаций", "Фиксированный купон · выплаты каждые шесть месяцев · цена меняется на рынке"))
        self.summary = QLabel("Доступно: —")
        self.summary.setStyleSheet("font-size: 16px; font-weight: bold;")
        layout.addWidget(self.summary)
        self.market = QTableWidget(0, 8)
        self.market.setHorizontalHeaderLabels(["Тикер", "Эмитент", "Тип", "Цена", "Купон годовых", "Выплата за штуку", "Следующий купон", "Погашение"])
        configure_table(self.market)
        self.market.itemSelectionChanged.connect(self.update_selected)
        layout.addWidget(wrap(self.market), 3)
        trade = QGroupBox("Сделка с облигациями")
        form = QHBoxLayout(trade)
        self.selected = QLabel("Выбери выпуск")
        self.quantity = QDoubleSpinBox()
        self.quantity.setRange(1, 1_000_000)
        self.quantity.setDecimals(0)
        self.quantity.setValue(1)
        buy = QPushButton("Купить")
        buy.setObjectName("Buy")
        sell = QPushButton("Продать")
        sell.setObjectName("Sell")
        buy.clicked.connect(lambda: self.execute_trade("BUY"))
        sell.clicked.connect(lambda: self.execute_trade("SELL"))
        form.addWidget(self.selected, 2)
        form.addWidget(QLabel("Количество:"))
        form.addWidget(self.quantity)
        form.addWidget(buy)
        form.addWidget(sell)
        layout.addWidget(trade)
        layout.addWidget(section("Мои облигации"))
        self.holdings = QTableWidget(0, 7)
        self.holdings.setHorizontalHeaderLabels(["Тикер", "Выпуск", "Количество", "Средняя цена", "Рыночная стоимость", "Купон за полгода", "Погашение"])
        configure_table(self.holdings)
        layout.addWidget(wrap(self.holdings), 2)
        self.selected_ticker = None
        self.timer = QTimer(self)
        self.timer.setInterval(30000)
        self.timer.timeout.connect(self.move_bond_market)
        self.timer.start()

    def process_coupon_payments(self, conn):
        today = date.today()
        due = conn.execute("SELECT * FROM bonds WHERE next_coupon_date<=? AND next_coupon_date<maturity_date", (today.isoformat(),)).fetchall()
        from dateutil.relativedelta import relativedelta
        for bond in due:
            holding = conn.execute("SELECT quantity FROM bond_holdings WHERE ticker=?", (bond["ticker"],)).fetchone()
            quantity = float(holding["quantity"]) if holding else 0.0
            if quantity > 0:
                amount = int(round(quantity * bond["face_value_cents"] * bond["coupon_rate"] / 100 / 2))
                conn.execute("INSERT INTO bond_coupon_payments(payment_date,ticker,quantity,amount_cents) VALUES(?,?,?,?)",
                             (bond["next_coupon_date"], bond["ticker"], quantity, amount))
            next_date = date.fromisoformat(bond["next_coupon_date"]) + relativedelta(months=6)
            conn.execute("UPDATE bonds SET next_coupon_date=? WHERE ticker=?", (next_date.isoformat(), bond["ticker"]))

    def refresh(self):
        with connect() as conn:
            self.process_coupon_payments(conn)
            rows = conn.execute("SELECT * FROM bonds ORDER BY issuer_type,ticker").fetchall()
            positions = conn.execute("""
                SELECT h.*,b.name,b.price_cents,b.face_value_cents,b.coupon_rate,b.maturity_date
                FROM bond_holdings h JOIN bonds b ON b.ticker=h.ticker
                WHERE h.quantity>0 ORDER BY h.ticker
            """).fetchall()
            cash = cash_balance(conn)
            record_financial_snapshot(conn)
        self.summary.setText(f"Доступно на счёте: {money(cash)}")
        self.market.setRowCount(len(rows))
        for r,b in enumerate(rows):
            semi = int(round(b["face_value_cents"] * b["coupon_rate"] / 100 / 2))
            vals=[b["ticker"],b["name"],b["issuer_type"],money(b["price_cents"]),
                  f"{b['coupon_rate']:.2f}%",money(semi),b["next_coupon_date"],b["maturity_date"]]
            for c,v in enumerate(vals): put(self.market,r,c,v)
            if b["ticker"]==self.selected_ticker: self.market.selectRow(r)
        self.holdings.setRowCount(len(positions))
        for r,h in enumerate(positions):
            semi=int(round(h["quantity"]*h["face_value_cents"]*h["coupon_rate"]/100/2))
            vals=[h["ticker"],h["name"],f"{h['quantity']:.0f}",money(h["average_price_cents"]),
                  money(int(h["quantity"]*h["price_cents"])),money(semi),h["maturity_date"]]
            for c,v in enumerate(vals): put(self.holdings,r,c,v)
        self.update_selected()

    def update_selected(self):
        row=self.market.currentRow()
        if row>=0 and self.market.item(row,0):
            self.selected_ticker=self.market.item(row,0).text()
            self.selected.setText("Выбрано: "+self.selected_ticker)

    def move_bond_market(self):
        import random
        with connect() as conn:
            rows=conn.execute("SELECT ticker,price_cents,volatility FROM bonds").fetchall()
            for bond in rows:
                # Небольшое ежедневное изменение цены; размер купона от этого не меняется.
                shock=random.gauss(0,bond["volatility"])
                new_price=max(1,int(round(bond["price_cents"]*(1+shock))))
                conn.execute("UPDATE bonds SET previous_price_cents=price_cents,price_cents=? WHERE ticker=?",
                             (new_price,bond["ticker"]))
            self.process_coupon_payments(conn)
            record_financial_snapshot(conn)
        self.refresh()

    def execute_trade(self, side):
        ticker=self.selected_ticker
        if not ticker:
            QMessageBox.warning(self,"Облигация не выбрана","Сначала выбери выпуск.")
            return
        qty=int(self.quantity.value())
        try:
            with connect() as conn:
                bond=conn.execute("SELECT * FROM bonds WHERE ticker=?",(ticker,)).fetchone()
                holding=conn.execute("SELECT * FROM bond_holdings WHERE ticker=?",(ticker,)).fetchone()
                price=bond["price_cents"]
                total=price*qty
                cash=cash_balance(conn)
                held=float(holding["quantity"]) if holding else 0.0
                if side=="BUY":
                    if cash<total: raise ValueError(f"Недостаточно средств. Не хватает {money(total-cash)}.")
                    new_qty=held+qty
                    avg=int(round((held*holding["average_price_cents"]+qty*price)/new_qty)) if new_qty else 0
                else:
                    if held<qty: raise ValueError(f"Недостаточно облигаций. В наличии: {held:.0f}.")
                    new_qty=held-qty
                    avg=holding["average_price_cents"] if new_qty else 0
                conn.execute("UPDATE bond_holdings SET quantity=?,average_price_cents=? WHERE ticker=?",
                             (new_qty,avg,ticker))
                conn.execute("INSERT INTO bond_trades(trade_date,ticker,side,quantity,price_cents,total_cents) VALUES(?,?,?,?,?,?)",
                             (date.today().isoformat(),ticker,side,qty,price,total))
                record_financial_snapshot(conn)
            self.refresh()
        except Exception as exc:
            QMessageBox.warning(self,"Ошибка сделки",str(exc))

class DepositPage(QWidget):
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.addLayout(heading("Калькулятор вклада", ""))
        box = QGroupBox("Параметры")
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
        self.result.setStyleSheet("font-size: 24px; color: #dde0e4; font-family: Helvetica, Arial, sans-serif; font-weight: bold;")
        self.interest = QLabel("")
        calc = QPushButton("Рассчитать")
        calc.setObjectName("Action")
        calc.clicked.connect(self.calculate)
        form.addRow("Начальная сумма", self.principal)
        form.addRow("Годовая ставка (%)", self.rate)
        form.addRow("Срок (лет)", self.years)
        form.addRow("Капитализация", self.compounds)
        form.addRow("", calc)
        layout.addWidget(box)
        layout.addWidget(section("Прогноз баланса"))
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
    """Сценарное моделирование текущего капитала пользователя."""
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.addLayout(heading("Моделирование капитала", "Прогноз на основе фактического баланса и текущей стоимости портфеля"))

        current_box = QGroupBox("Текущая финансовая позиция")
        current_row = QHBoxLayout(current_box)
        self.cash_value = metric("Деньги на счёте", "—")
        self.portfolio_value = metric("Инвестиционный портфель", "—")
        self.total_value = metric("Стартовый капитал", "—", hero=True)
        for item in (self.cash_value, self.portfolio_value, self.total_value):
            current_row.addWidget(item, 1)
        layout.addWidget(current_box)

        box = QGroupBox("Параметры сценария")
        form = QFormLayout(box)
        self.rate = QDoubleSpinBox()
        self.rate.setRange(-99, 100)
        self.rate.setDecimals(2)
        self.rate.setValue(8)
        self.volatility = QDoubleSpinBox()
        self.volatility.setRange(0, 100)
        self.volatility.setDecimals(2)
        self.volatility.setValue(18)
        self.years = QSpinBox()
        self.years.setRange(1, 50)
        self.years.setValue(10)
        self.simulations = QSpinBox()
        self.simulations.setRange(100, 10000)
        self.simulations.setSingleStep(500)
        self.simulations.setValue(1000)
        self.contribution = QDoubleSpinBox()
        self.contribution.setRange(0, 1_000_000_000)
        self.contribution.setDecimals(2)
        self.contribution.setSuffix(" ₽ / мес.")
        self.contribution.setValue(0)
        form.addRow("Ожидаемая доходность инвестиций в год (%)", self.rate)
        form.addRow("Волатильность инвестиций в год (%)", self.volatility)
        form.addRow("Ежемесячное пополнение портфеля", self.contribution)
        form.addRow("Горизонт (лет)", self.years)
        form.addRow("Количество сценариев", self.simulations)
        run = QPushButton("Рассчитать сценарии")
        run.setObjectName("Action")
        run.clicked.connect(self.run_projection)
        form.addRow("", run)
        layout.addWidget(box)

        layout.addWidget(section("Результат моделирования"))
        self.output = QLabel("—")
        self.output.setStyleSheet("font-size: 22px; color: #dde0e4; font-family: Helvetica, Arial, sans-serif; font-weight: bold;")
        self.details = QLabel("Параметры доходности — допущения для сценария, а не обещание результата.")
        self.details.setWordWrap(True)
        layout.addWidget(self.output)
        layout.addWidget(self.details)

        self.figure = Figure(figsize=(8, 3.5), dpi=90, facecolor=SURFACE)
        self.canvas = FigureCanvas(self.figure)
        self.axes = self.figure.add_subplot(111)
        style_axes(self.axes)
        layout.addWidget(self.canvas, 1)
        self._cash_cents = 0
        self._portfolio_cents = 0

    def refresh(self):
        with connect() as conn:
            self._cash_cents = cash_balance(conn)
            manual = conn.execute("""
                SELECT COALESCE(SUM(CAST(ROUND(a.quantity*a.current_price_cents) AS INTEGER)),0)
                FROM assets a
                WHERE NOT EXISTS (
                    SELECT 1 FROM holdings h
                    WHERE h.ticker=UPPER(a.ticker) AND h.quantity>0
                )
            """).fetchone()[0]
            market = conn.execute("""
                SELECT COALESCE(SUM(CAST(ROUND(h.quantity*s.price_cents) AS INTEGER)),0)
                FROM holdings h JOIN stocks s ON s.ticker=h.ticker
                WHERE h.quantity>0
            """).fetchone()[0]
            self._portfolio_cents = int(manual + market)
        total = self._cash_cents + self._portfolio_cents
        self.cash_value.value_label.setText(money(self._cash_cents))
        self.portfolio_value.value_label.setText(money(self._portfolio_cents))
        self.total_value.value_label.setText(money(total))
        self.output.setText("—")
        self.details.setText("Текущие значения обновлены. Настрой параметры и рассчитай сценарии.")
        self.axes.clear()
        style_axes(self.axes)
        self.axes.text(0.5, 0.5, "График появится после расчёта",
                       color=MUTED, ha="center", va="center", transform=self.axes.transAxes)
        self.canvas.draw_idle()

    def run_projection(self):
        try:
            if self._cash_cents + self._portfolio_cents <= 0:
                self.refresh()
            result = monte_carlo_capital(
                self._cash_cents,
                self._portfolio_cents,
                self.rate.value(),
                self.volatility.value(),
                self.years.value(),
                self.simulations.value(),
                to_cents(self.contribution.value()) if self.contribution.value() > 0 else 0,
            )
            self.output.setText(f"Медианный капитал через {self.years.value()} лет: {money(result['median'])}")
            self.details.setText(
                f"Среднее: {money(result['average'])} · "
                f"Нижний сценарий (5%): {money(result['p5'])} · "
                f"Верхний сценарий (95%): {money(result['p95'])}\\n"
                f"Вероятность оказаться ниже текущего капитала: {result['loss_probability']:.1f}%. "
                f"В расчёте участвуют фактический баланс и текущая стоимость портфеля."
            )

            ax = self.axes
            ax.clear()
            ax.set_facecolor(SURFACE)
            years = result["years"]
            ax.fill_between(years, result["p5_path"], result["p95_path"],
                            color=ACCENT, alpha=0.18, label="Диапазон 5–95%")
            ax.plot(years, result["median_path"], color=ACCENT,
                    linewidth=2.2, label="Медианный сценарий")
            ax.plot(years, result["p5_path"], color=DOWN, linewidth=1,
                    linestyle="--", label="5-й процентиль")
            ax.plot(years, result["p95_path"], color=UP, linewidth=1,
                    linestyle="--", label="95-й процентиль")
            ax.set_xlabel("Годы", color=MUTED, fontsize=9)
            ax.set_ylabel("Общий капитал, ₽", color=MUTED, fontsize=9)
            ax.yaxis.set_major_formatter(lambda value, _pos: f"{value:,.0f}".replace(",", " "))
            ax.legend(frameon=False, labelcolor=MUTED, fontsize=8)
            style_axes(ax)
            self.figure.tight_layout()
            self.canvas.draw_idle()

            with connect() as conn:
                conn.execute(
                    "INSERT INTO simulation_runs(initial_cents,annual_rate,years,final_cents) VALUES(?,?,?,?)",
                    (self._cash_cents + self._portfolio_cents, self.rate.value(),
                     self.years.value(), result["average"])
                )
        except Exception as exc:
            QMessageBox.warning(self, "Ошибка моделирования", str(exc))


class ReportsPage(QWidget):
    """Аналитика, построенная непосредственно по истории операций и портфелю."""
    def __init__(self):
        super().__init__()
        outer = QVBoxLayout(self)
        outer.addLayout(heading("Отчёты", "Финансовая аналитика по операциям и инвестициям"))

        filter_row = QHBoxLayout()
        filter_row.addWidget(QLabel("Период отчёта"))
        self.period = QComboBox()
        self.period.addItem("Всё время", 0)
        self.period.addItem("Последние 30 дней", 30)
        self.period.addItem("Последние 90 дней", 90)
        self.period.addItem("Последние 12 месяцев", 365)
        self.period.addItem("Текущий год", -1)
        self.period.setCurrentIndex(0)
        self.period.currentIndexChanged.connect(lambda _=None: self.refresh())
        filter_row.addWidget(self.period)
        filter_row.addStretch()
        outer.addLayout(filter_row)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        outer.addWidget(scroll, 1)
        body = QWidget()
        scroll.setWidget(body)
        layout = QVBoxLayout(body)
        layout.setContentsMargins(0, 8, 8, 8)
        layout.setSpacing(12)

        metrics_top = QHBoxLayout()
        self.income_metric = metric("Поступления за период", "—")
        self.expense_metric = metric("Списания за период", "—")
        self.net_metric = metric("Денежный поток", "—", hero=True)
        self.balance_metric = metric("Текущий баланс", "—")
        for item in (self.income_metric, self.expense_metric,
                     self.net_metric, self.balance_metric):
            metrics_top.addWidget(item, 1)
        layout.addLayout(metrics_top)

        metrics_bottom = QHBoxLayout()
        self.invested_metric = metric("Вложено в портфель", "—")
        self.value_metric = metric("Текущая стоимость портфеля", "—")
        self.pnl_metric = metric("Прибыль / убыток по открытым позициям", "—")
        self.realized_metric = metric("Результат закрытых сделок", "—")
        for item in (self.invested_metric, self.value_metric, self.pnl_metric, self.realized_metric):
            metrics_bottom.addWidget(item, 1)
        layout.addLayout(metrics_bottom)

        charts = QHBoxLayout()
        flow_box = QGroupBox("Движение денег по месяцам")
        flow_layout = QVBoxLayout(flow_box)
        self.flow_figure = Figure(figsize=(7, 3), dpi=90, facecolor=SURFACE)
        self.flow_canvas = FigureCanvas(self.flow_figure)
        self.flow_axes = self.flow_figure.add_subplot(111)
        flow_layout.addWidget(self.flow_canvas)
        category_box = QGroupBox("Структура списаний по категориям")
        category_layout = QVBoxLayout(category_box)
        self.category_figure = Figure(figsize=(5, 3), dpi=90, facecolor=SURFACE)
        self.category_canvas = FigureCanvas(self.category_figure)
        self.category_axes = self.category_figure.add_subplot(111)
        category_layout.addWidget(self.category_canvas)
        charts.addWidget(flow_box, 3)
        charts.addWidget(category_box, 2)
        layout.addLayout(charts)

        history_box = QGroupBox("История общего капитала и портфеля")
        history_layout = QVBoxLayout(history_box)
        self.history_figure = Figure(figsize=(9, 3), dpi=90, facecolor=SURFACE)
        self.history_canvas = FigureCanvas(self.history_figure)
        self.history_axes = self.history_figure.add_subplot(111)
        history_layout.addWidget(self.history_canvas)
        layout.addWidget(history_box)

        layout.addWidget(section("Сводка по типам операций"))
        self.breakdown = QTableWidget(0, 3)
        self.breakdown.setHorizontalHeaderLabels(["Тип операции", "Количество", "Сумма"])
        configure_table(self.breakdown)
        layout.addWidget(wrap(self.breakdown))

        layout.addWidget(section("История операций за выбранный период"))
        self.history = QTableWidget(0, 5)
        self.history.setHorizontalHeaderLabels(["Дата", "Тип", "Категория", "Описание", "Сумма"])
        configure_table(self.history)
        layout.addWidget(wrap(self.history))

        self.note = QLabel("Поступления и списания включают банковские операции и сделки с акциями. "
                           "Текущий баланс и оценка портфеля показывают состояние на сегодня.")
        self.note.setWordWrap(True)
        self.note.setObjectName("Muted")
        layout.addWidget(self.note)

    def _period_start(self):
        days = self.period.currentData()
        if days == 0:
            return None
        today = date.today()
        if days == -1:
            return date(today.year, 1, 1).isoformat()
        return (today - timedelta(days=days - 1)).isoformat()

    def _portfolio_totals(self, conn):
        manual = conn.execute("SELECT * FROM assets ORDER BY name").fetchall()
        market = conn.execute("""
            SELECT s.name, h.ticker, h.quantity, h.average_price_cents, s.price_cents
            FROM holdings h JOIN stocks s ON s.ticker=h.ticker
            WHERE h.quantity > 0 ORDER BY h.ticker
        """).fetchall()
        market_tickers = {row["ticker"].upper() for row in market}
        positions = [
            (row["quantity"], row["average_price_cents"], row["current_price_cents"])
            for row in manual
            if not row["ticker"] or row["ticker"].upper() not in market_tickers
        ]
        positions.extend(
            (row["quantity"], row["average_price_cents"], row["price_cents"])
            for row in market
        )
        cost = sum(int(qty * avg) for qty, avg, _ in positions)
        value = sum(int(qty * current) for qty, _, current in positions)
        return cost, value

    def _draw_flow_chart(self, operations):
        monthly = {}
        for operation in operations:
            month = operation["date"][:7]
            bucket = monthly.setdefault(month, [0, 0])
            if operation["delta"] >= 0:
                bucket[0] += operation["delta"]
            else:
                bucket[1] += -operation["delta"]

        ax = self.flow_axes
        ax.clear()
        ax.set_facecolor(SURFACE)
        if not monthly:
            ax.text(0.5, 0.5, "Нет операций за выбранный период",
                    color=MUTED, ha="center", va="center", transform=ax.transAxes)
            style_axes(ax)
            ax.set_xticks([])
            self.flow_canvas.draw_idle()
            return

        months = sorted(monthly)
        incoming = [monthly[m][0] / 100 for m in months]
        outgoing = [monthly[m][1] / 100 for m in months]
        x = list(range(len(months)))
        width = 0.38
        ax.bar([v - width / 2 for v in x], incoming, width=width,
               color=UP, label="Поступления")
        ax.bar([v + width / 2 for v in x], outgoing, width=width,
               color=DOWN, label="Списания")
        ax.set_xticks(x)
        ax.set_xticklabels(months, rotation=30, ha="right", color=MUTED, fontsize=8)
        ax.legend(frameon=False, labelcolor=MUTED, fontsize=8)
        ax.yaxis.set_major_formatter(lambda value, _pos: f"{value:,.0f}".replace(",", " "))
        style_axes(ax)
        self.flow_figure.tight_layout()
        self.flow_canvas.draw_idle()

    def _draw_category_chart(self, operations):
        categories = {}
        for operation in operations:
            if operation["delta"] < 0:
                categories[operation["category"]] = (
                    categories.get(operation["category"], 0) - operation["delta"]
                )
        ax = self.category_axes
        ax.clear()
        ax.set_facecolor(SURFACE)
        if not categories:
            ax.text(0.5, 0.5, "Нет списаний за выбранный период",
                    color=MUTED, ha="center", va="center", transform=ax.transAxes)
            ax.axis("off")
            self.category_canvas.draw_idle()
            return

        ranked = sorted(categories.items(), key=lambda item: item[1], reverse=True)
        if len(ranked) > 6:
            top = ranked[:5]
            other = sum(value for _, value in ranked[5:])
            ranked = top + [("Прочее", other)]
        labels = [name for name, _ in ranked]
        values = [value / 100 for _, value in ranked]
        ax.pie(values, labels=labels, autopct="%1.0f%%", startangle=90,
               colors=PIE[:len(values)],
               textprops={"color": TEXT, "fontsize": 8},
               wedgeprops={"edgecolor": SURFACE, "linewidth": 1})
        ax.set_aspect("equal")
        self.category_figure.tight_layout()
        self.category_canvas.draw_idle()

    def _draw_history_chart(self, snapshots):
        ax = self.history_axes
        ax.clear()
        ax.set_facecolor(SURFACE)
        # Для читаемости показываем последний согласованный снимок каждого дня.
        daily = {}
        for row in snapshots:
            daily[row["captured_at"][:10]] = row
        dates = sorted(daily)
        if not dates:
            ax.text(0.5, 0.5, "История капитала начнёт накапливаться после изменений в счёте или портфеле",
                    color=MUTED, ha="center", va="center", transform=ax.transAxes)
            style_axes(ax)
            ax.set_xticks([])
            self.history_canvas.draw_idle()
            return
        x = list(range(len(dates)))
        net_worth = [daily[key]["net_worth_cents"] / 100 for key in dates]
        portfolio = [daily[key]["portfolio_value_cents"] / 100 for key in dates]
        ax.plot(x, net_worth, marker="o" if len(x) < 20 else None,
                linewidth=2, color=ACCENT, label="Общий капитал")
        ax.plot(x, portfolio, marker="o" if len(x) < 20 else None,
                linewidth=1.6, color=UP, label="Портфель")
        ax.set_xticks(x)
        step = max(1, len(dates) // 10)
        ax.set_xticklabels([d if i % step == 0 or i == len(dates)-1 else ""
                            for i, d in enumerate(dates)],
                           rotation=30, ha="right", color=MUTED, fontsize=8)
        ax.yaxis.set_major_formatter(lambda value, _pos: f"{value:,.0f}".replace(",", " "))
        ax.legend(frameon=False, labelcolor=MUTED, fontsize=8)
        ax.set_ylabel("Рубли", color=MUTED, fontsize=8)
        style_axes(ax)
        self.history_figure.tight_layout()
        self.history_canvas.draw_idle()

    def refresh(self):
        start = self._period_start()
        with connect() as conn:
            all_operations = operation_rows(conn)
            balance = cash_balance(conn)
            cost, portfolio_value = self._portfolio_totals(conn)
            snapshots = conn.execute(
                "SELECT * FROM financial_snapshots ORDER BY captured_at"
            ).fetchall()
            realized_query = "SELECT COALESCE(SUM(realized_pnl_cents),0) FROM trades"
            realized_params = ()
            if start is not None:
                realized_query += " WHERE trade_date >= ?"
                realized_params = (start,)
            realized_pnl = conn.execute(realized_query, realized_params).fetchone()[0]

        operations = [
            row for row in all_operations
            if start is None or row["date"] >= start
        ]
        income = sum(row["delta"] for row in operations if row["delta"] > 0)
        expense = -sum(row["delta"] for row in operations if row["delta"] < 0)
        net = income - expense
        pnl = portfolio_value - cost

        self.income_metric.value_label.setText(money(income))
        self.expense_metric.value_label.setText(money(expense))
        self.net_metric.value_label.setText(("+" if net > 0 else "") + money(net))
        self.balance_metric.value_label.setText(money(balance))
        self.invested_metric.value_label.setText(money(cost))
        self.value_metric.value_label.setText(money(portfolio_value))
        self.pnl_metric.value_label.setText(("+" if pnl > 0 else "") + money(pnl))
        self.realized_metric.value_label.setText(
            ("+" if realized_pnl > 0 else "") + money(realized_pnl)
        )

        grouped = {}
        for row in operations:
            item = grouped.setdefault(row["type"], [0, 0])
            item[0] += 1
            item[1] += abs(row["delta"])
        breakdown_rows = sorted(grouped.items(), key=lambda item: item[0])
        self.breakdown.setRowCount(len(breakdown_rows))
        for r, (kind, values) in enumerate(breakdown_rows):
            for c, value in enumerate((kind, values[0], money(values[1]))):
                put(self.breakdown, r, c, value)

        self.history.setRowCount(len(operations))
        for r, row in enumerate(operations):
            values = [row["date"], row["type"], row["category"],
                      row["description"], row["amount"]]
            for c, value in enumerate(values):
                put(self.history, r, c, value)

        self._draw_flow_chart(operations)
        self._draw_category_chart(operations)
        filtered_snapshots = [
            row for row in snapshots
            if start is None or row["captured_at"][:10] >= start
        ]
        self._draw_history_chart(filtered_snapshots)


class StockMarketPage(QWidget):
    """Локальный рынок с Монте-Карло моделированием котировок."""
    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.addLayout(heading("Рынок акций", "32 компании · учебные котировки с независимой волатильностью"))
        summary = QHBoxLayout()
        self.cash_label = QLabel("Доступно: —")
        self.cash_label.setStyleSheet("font-size: 16px; font-weight: bold; color: #dde0e4; font-family: Helvetica, Arial, sans-serif;")
        self.portfolio_label = QLabel("Стоимость акций: —")
        self.portfolio_label.setStyleSheet("font-size: 16px; font-weight: bold;")
        summary.addWidget(self.cash_label)
        summary.addStretch()
        summary.addWidget(self.portfolio_label)
        layout.addLayout(summary)

        market_box = QGroupBox("Котировки")
        market_layout = QVBoxLayout(market_box)
        self.market = QTableWidget(0, 5)
        self.market.setHorizontalHeaderLabels(["Тикер", "Компания", "Цена", "Изменение", "Изменение, %"])
        configure_table(self.market)
        self.market.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.market.itemSelectionChanged.connect(self.update_selected_price)
        market_layout.addWidget(self.market)
        layout.addWidget(market_box, 3)

        trade_box = QGroupBox("Совершить сделку")
        trade_form = QHBoxLayout(trade_box)
        self.selected_stock = QLabel("Выбери акцию в таблице выше")
        self.selected_stock.setMinimumWidth(170)
        self.quantity = QDoubleSpinBox()
        self.quantity.setRange(0.01, 1_000_000)
        self.quantity.setDecimals(2)
        self.quantity.setSingleStep(1.0)
        self.quantity.setValue(1.0)
        buy = QPushButton("Купить")
        buy.setObjectName("Buy")
        sell = QPushButton("Продать")
        sell.setObjectName("Sell")
        buy.clicked.connect(lambda: self.execute_trade("BUY"))
        sell.clicked.connect(lambda: self.execute_trade("SELL"))
        trade_form.addWidget(self.selected_stock, 2)
        trade_form.addWidget(QLabel("Количество:"))
        trade_form.addWidget(self.quantity)
        trade_form.addWidget(buy)
        trade_form.addWidget(sell)
        layout.addWidget(trade_box)

        layout.addWidget(section("Мои акции"))
        self.holdings_table = QTableWidget(0, 7)
        self.holdings_table.setHorizontalHeaderLabels(["Тикер", "Компания", "Количество", "Средняя покупка", "Текущая стоимость", "Прибыль / убыток", "Прибыль / убыток, %"])
        configure_table(self.holdings_table)
        layout.addWidget(wrap(self.holdings_table), 2)

        self.timer = QTimer(self)
        self.timer.setInterval(15000)
        self.timer.timeout.connect(self.move_market)
        self.timer.start()
        self.selected_ticker = None

    def cash_balance(self, conn):
        return cash_balance(conn)

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
            vals = [stock["ticker"], stock["name"], money(stock["price_cents"]), ("+" if change > 0 else "") + money(change), f"{pct:+.2f}%"]
            for c, value in enumerate(vals):
                put(self.market, r, c, value, (UP if change >= 0 else DOWN) if c >= 3 else None, c == 0)
            if stock["ticker"] == selected:
                self.market.selectRow(r)
        self.holdings_table.setRowCount(len(holdings))
        for r, h in enumerate(holdings):
            current_value = int(h["quantity"] * h["price_cents"])
            cost_value = int(h["quantity"] * h["average_price_cents"])
            pnl = current_value - cost_value
            pnl_pct = (pnl / cost_value * 100) if cost_value else 0.0
            vals = [h["ticker"], h["name"], f"{h['quantity']:.2f}",
                    money(h["average_price_cents"]), money(current_value),
                    ("+" if pnl > 0 else "") + money(pnl), f"{pnl_pct:+.2f}%"]
            for c, value in enumerate(vals):
                put(self.holdings_table, r, c, value)
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
        # Каждые 15 секунд симулятор проигрывает один условный торговый день.
        # Для каждой акции генерируется независимый сценарий Монте-Карло (GBM).
        with connect() as conn:
            rows = conn.execute("SELECT ticker, price_cents, volatility FROM stocks").fetchall()
            for stock in rows:
                new_price = monte_carlo_price_step(
                    stock["price_cents"],
                    stock["volatility"],
                    annual_return_percent=8.0,
                )
                conn.execute(
                    "UPDATE stocks SET previous_price_cents=price_cents, "
                    "price_cents=?, updated_at=CURRENT_TIMESTAMP WHERE ticker=?",
                    (new_price, stock["ticker"]),
                )
            record_financial_snapshot(conn)
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
                        shortfall = total - cash
                        raise ValueError(
                            f"Недостаточно средств для покупки.\n"
                            f"Не хватает: {money(shortfall)}."
                        )
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
                realized_pnl = int(round(quantity * (price - holding["average_price_cents"]))) if side == "SELL" else 0
                conn.execute(
                    """INSERT INTO trades(
                           trade_date,ticker,side,quantity,price_cents,total_cents,realized_pnl_cents
                       ) VALUES(?,?,?,?,?,?,?)""",
                    (date.today().isoformat(), ticker, side, quantity, price, total, realized_pnl)
                )
                record_financial_snapshot(conn)
            action = "Куплено" if side == "BUY" else "Продано"
            QMessageBox.information(self, "Сделка выполнена", f"{action} {quantity:.2f} акций {ticker} по {money(price)} за штуку.\nСумма: {money(total)}.")
            self.refresh()
        except Exception as exc:
            QMessageBox.warning(self, "Не удалось совершить сделку", str(exc))
