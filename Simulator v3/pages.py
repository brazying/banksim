from datetime import date, datetime, timedelta
import calendar


def add_months(value, months):
    month_index = value.month - 1 + months
    year = value.year + month_index // 12
    month = month_index % 12 + 1
    day = min(value.day, calendar.monthrange(year, month)[1])
    return value.replace(year=year, month=month, day=day)
from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QTableWidget,
    QTableWidgetItem, QHeaderView, QLineEdit, QComboBox, QDoubleSpinBox, QSpinBox, QFormLayout,
    QMessageBox, QGroupBox, QFrame, QScrollArea)
from PyQt6.QtCore import Qt
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
from database import connect, record_financial_snapshot, simulated_datetime, cash_balance, portfolio_totals
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
    if subtitle:
        subtitle_label = QLabel(subtitle)
        subtitle_label.setObjectName("PageSub")
        subtitle_label.setWordWrap(True)
        box.addWidget(subtitle_label)
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

def operation_rows(conn):
    rows = []
    transactions = conn.execute("SELECT * FROM transactions").fetchall()
    trades = conn.execute("SELECT * FROM trades").fetchall()
    bond_trades = conn.execute("SELECT * FROM bond_trades").fetchall()
    coupons = conn.execute("SELECT * FROM bond_coupon_payments").fetchall()
    redemptions = conn.execute("SELECT * FROM bond_redemptions").fetchall()

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
    for row in redemptions:
        rows.append({
            "date": row["payment_date"], "id": row["id"], "source": 4,
            "type": "Погашение облигации", "category": "Погашение",
            "description": row["ticker"] + " · возврат номинала",
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
        capital_box = QGroupBox("История общего капитала")
        capital_layout = QVBoxLayout(capital_box)
        self.capital_chart = CapitalChart()
        capital_layout.addWidget(self.capital_chart)
        allocation_box = QGroupBox("Структура активов")
        allocation_layout = QVBoxLayout(allocation_box)
        self.allocation_chart = AllocationChart()
        allocation_layout.addWidget(self.allocation_chart)
        self.capital_chart.setMinimumHeight(250)
        self.allocation_chart.setMinimumHeight(250)
        capital_box.setMinimumHeight(290)
        allocation_box.setMinimumHeight(290)
        charts_row.addWidget(capital_box, 2)
        charts_row.addWidget(allocation_box, 1)
        layout.addLayout(charts_row, 3)
        layout.addWidget(section("Последние операции"))
        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(["Дата", "Тип", "Категория", "Описание", "Сумма"])
        configure_table(self.table)
        self.table.setMinimumHeight(150)
        layout.addWidget(wrap(self.table), 1)

    def refresh(self):
        with connect() as conn:
            rows = operation_rows(conn)[:8]
            balance = cash_balance(conn)
            snapshots = conn.execute(
                "SELECT captured_at, net_worth_cents FROM financial_snapshots ORDER BY captured_at"
            ).fetchall()
            positions, _, portfolio = portfolio_totals(conn)
        assets = [
            {"name": name + (f" ({ticker})" if ticker else ""),
             "quantity": quantity, "current_price_cents": current}
            for name, ticker, quantity, _, current, _ in positions
        ]
        self.balance.value_label.setText(money(balance))
        self.portfolio.value_label.setText(money(portfolio))
        self.net.value_label.setText(money(balance + portfolio))
        recent_snapshots = snapshots[-30:]
        labels = [
            datetime.fromisoformat(row["captured_at"]).strftime("%d.%m %H:%M")
            for row in recent_snapshots
        ]
        values = [row["net_worth_cents"] / 100 for row in recent_snapshots]
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
                tx_date = simulated_datetime(conn).isoformat(timespec="seconds")
                conn.execute("INSERT INTO transactions(tx_date,tx_type,category,description,amount_cents) VALUES(?,?,?,?,?)",
                    (tx_date, tx_type, category, self.description.text().strip(), cents))
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
        asset_note = QLabel("Ручное добавление актива учитывает его стоимость в портфеле, но не списывает деньги со счёта. Для реальной покупки используй вкладки биржи или облигаций.")
        asset_note.setWordWrap(True)
        asset_note.setObjectName("Muted")
        layout.addWidget(asset_note)
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
            positions, _, _ = portfolio_totals(conn)

        self.table.setRowCount(len(positions))
        for r, row in enumerate(positions):
            name, ticker, qty, avg_price, current_price, _kind = row
            current_value = int(round(qty * current_price))
            cost_value = int(round(qty * avg_price))
            pnl = current_value - cost_value
            pnl_pct = (pnl / cost_value * 100) if cost_value else 0.0
            vals = [name, ticker, f"{qty:g}", money(avg_price), money(current_price),
                    ("+" if pnl > 0 else "") + money(pnl), f"{pnl_pct:+.2f}%"]
            for c, value in enumerate(vals):
                put(self.table, r, c, value)

class BondsPage(QWidget):
    """Учебный рынок облигаций с плавающей рыночной ценой и полугодовыми купонами."""    def __init__(self):
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

    def process_coupon_payments(self, conn):
        today = simulated_datetime(conn).date()
        bonds = conn.execute("SELECT * FROM bonds").fetchall()
        for bond in bonds:
            next_date = date.fromisoformat(bond["next_coupon_date"])
            maturity = date.fromisoformat(bond["maturity_date"])
            holding = conn.execute(
                "SELECT quantity,average_price_cents FROM bond_holdings WHERE ticker=?", (bond["ticker"],)
            ).fetchone()
            current_quantity = float(holding["quantity"]) if holding else 0.0
            average_price = int(holding["average_price_cents"]) if holding else 0

            # Купон получает количество облигаций, находившееся в портфеле на дату выплаты.
            while next_date <= today and next_date <= maturity:
                payment_cutoff = next_date.isoformat() + "T00:00:00"
                eligible = conn.execute(
                    """SELECT COALESCE(SUM(CASE WHEN side='BUY' THEN quantity ELSE -quantity END),0)
                       FROM bond_trades WHERE ticker=? AND trade_date<=?""",
                    (bond["ticker"], payment_cutoff)
                ).fetchone()[0]
                quantity = max(0.0, float(eligible or 0.0))
                if quantity > 0:
                    amount = int(round(
                        quantity * bond["face_value_cents"] * bond["coupon_rate"] / 100 / 2
                    ))
                    conn.execute(
                        "INSERT INTO bond_coupon_payments(payment_date,ticker,quantity,amount_cents) VALUES(?,?,?,?)",
                        (next_date.isoformat(), bond["ticker"], quantity, amount)
                    )
                next_date = add_months(next_date, 6)
                conn.execute(
                    "UPDATE bonds SET next_coupon_date=? WHERE ticker=?",
                    (next_date.isoformat(), bond["ticker"])
                )

            redemption_exists = conn.execute(
                "SELECT 1 FROM bond_redemptions WHERE ticker=? LIMIT 1", (bond["ticker"],)
            ).fetchone()
            if maturity <= today and current_quantity > 0 and not redemption_exists:
                redemption_cutoff = maturity.isoformat() + "T23:59:59"
                eligible = conn.execute(
                    """SELECT COALESCE(SUM(CASE WHEN side='BUY' THEN quantity ELSE -quantity END),0)
                       FROM bond_trades WHERE ticker=? AND trade_date<=?""",
                    (bond["ticker"], redemption_cutoff)
                ).fetchone()[0]
                quantity = max(0.0, float(eligible or 0.0))
                if quantity > 0:
                    redemption = int(round(quantity * bond["face_value_cents"]))
                    realized_pnl = int(round(quantity * (bond["face_value_cents"] - average_price)))
                    conn.execute(
                        """INSERT INTO bond_redemptions(
                               payment_date,ticker,quantity,amount_cents,realized_pnl_cents
                           ) VALUES(?,?,?,?,?)""",
                        (bond["maturity_date"], bond["ticker"], quantity, redemption, realized_pnl)
                    )
                conn.execute(
                    "UPDATE bond_holdings SET quantity=0,average_price_cents=0 WHERE ticker=?",
                    (bond["ticker"],)
                )

    def refresh(self):
        with connect() as conn:
            self.process_coupon_payments(conn)
            simulated_today = simulated_datetime(conn).date().isoformat()
            rows = conn.execute("SELECT * FROM bonds WHERE maturity_date>? ORDER BY issuer_type,ticker", (simulated_today,)).fetchall()
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
                  money(int(round(h["quantity"]*h["price_cents"]))),money(semi),h["maturity_date"]]
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
                # Небольшое почасовое изменение цены; размер купона от этого не меняется.
                shock=random.gauss(0,bond["volatility"] / (24 ** 0.5))
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
                simulated_today = simulated_datetime(conn).date().isoformat()
                if not bond or bond["maturity_date"] <= simulated_today:
                    raise ValueError("Срок обращения этого выпуска завершён.")
                # Начисляем наступившие купоны до изменения позиции.
                self.process_coupon_payments(conn)
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
                trade_date = simulated_datetime(conn).isoformat(timespec="seconds")
                realized_pnl = int(round(qty * (price - holding["average_price_cents"]))) if side == "SELL" else 0
                conn.execute(
                    """INSERT INTO bond_trades(
                           trade_date,ticker,side,quantity,price_cents,total_cents,realized_pnl_cents
                       ) VALUES(?,?,?,?,?,?,?)""",
                    (trade_date,ticker,side,qty,price,total,realized_pnl)
                )
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
        explanation = QLabel("Это расчётный сценарий: он не открывает вклад и не изменяет деньги на банковском счёте.")
        explanation.setWordWrap(True)
        explanation.setObjectName("Muted")
        layout.addWidget(explanation)
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
        contribution_note = QLabel(
            "Ежемесячные взносы добавляются к инвестициям как дополнительные внешние средства. "
            "Они не списываются с текущего банковского счёта, а его остаток в прогнозе остаётся неизменным."
        )
        contribution_note.setWordWrap(True)
        contribution_note.setObjectName("Muted")
        layout.addWidget(contribution_note)

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
        self._projection_basis = None

    def refresh_live_values(self):
        with connect() as conn:
            self._cash_cents = cash_balance(conn)
            _, _, self._portfolio_cents = portfolio_totals(conn)
        total = self._cash_cents + self._portfolio_cents
        self.cash_value.value_label.setText(money(self._cash_cents))
        self.portfolio_value.value_label.setText(money(self._portfolio_cents))
        self.total_value.value_label.setText(money(total))
        if self._projection_basis is not None and (self._cash_cents, self._portfolio_cents) != self._projection_basis:
            self.details.setText(
                "Текущая позиция изменилась после последнего расчёта. "
                "Результат на графике рассчитан по прежнему стартовому капиталу — пересчитай сценарий."
            )
        return total

    def refresh(self):
        self.refresh_live_values()
        # Не стираем уже рассчитанный сценарий при обычном переходе между вкладками.
        if self._projection_basis is None:
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
            self._projection_basis = (self._cash_cents, self._portfolio_cents)
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
    """Сводная аналитика денежных потоков, портфеля и инвестиционного результата."""    def __init__(self):
        super().__init__()
        outer = QVBoxLayout(self)
        outer.addLayout(heading("Отчёты", "Денежные потоки, инвестиционный результат и динамика капитала"))

        filters = QHBoxLayout()
        filters.addWidget(QLabel("Период операций и графиков:"))
        self.period = QComboBox()
        self.period.addItem("Всё время", 0)
        self.period.addItem("30 дней", 30)
        self.period.addItem("90 дней", 90)
        self.period.addItem("12 месяцев", 365)
        self.period.addItem("Текущий год", -1)
        self.period.currentIndexChanged.connect(lambda _=None: self.refresh())
        filters.addWidget(self.period)
        filters.addStretch()
        outer.addLayout(filters)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        outer.addWidget(scroll, 1)
        body = QWidget()
        scroll.setWidget(body)
        layout = QVBoxLayout(body)
        layout.setContentsMargins(0, 8, 8, 8)
        layout.setSpacing(14)

        row1 = QHBoxLayout()
        self.income_metric = metric("Поступления денег", "—")
        self.expense_metric = metric("Списания денег", "—")
        self.net_metric = metric("Чистый денежный поток", "—", hero=True)
        self.balance_metric = metric("Деньги на счёте · сейчас", "—")
        for item in (self.income_metric, self.expense_metric, self.net_metric, self.balance_metric):
            row1.addWidget(item, 1)
        layout.addLayout(row1)

        row2 = QHBoxLayout()
        self.buy_metric = metric("Покупки активов", "—")
        self.value_metric = metric("Стоимость портфеля · сейчас", "—")
        self.unrealized_metric = metric("Нереализованный P&L · сейчас", "—")
        self.realized_metric = metric("Реализованный P&L · период", "—")
        self.coupon_metric = metric("Купонный доход · период", "—")
        for item in (self.buy_metric, self.value_metric, self.unrealized_metric, self.realized_metric, self.coupon_metric):
            row2.addWidget(item, 1)
        layout.addLayout(row2)

        charts_top = QHBoxLayout()
        self.flow_figure, self.flow_axes, self.flow_canvas = self._make_chart((7, 3))
        self.expense_figure, self.expense_axes, self.expense_canvas = self._make_chart((5, 3))
        flow_box = QGroupBox("Денежные потоки по месяцам")
        flow_layout = QVBoxLayout(flow_box)
        flow_layout.addWidget(self.flow_canvas)
        expense_box = QGroupBox("Расходы по категориям · без покупок активов")
        expense_layout = QVBoxLayout(expense_box)
        expense_layout.addWidget(self.expense_canvas)
        charts_top.addWidget(flow_box, 3)
        charts_top.addWidget(expense_box, 2)
        layout.addLayout(charts_top)

        charts_bottom = QHBoxLayout()
        self.capital_figure, self.capital_axes, self.capital_canvas = self._make_chart((7, 3))
        self.allocation_figure, self.allocation_axes, self.allocation_canvas = self._make_chart((5, 3))
        capital_box = QGroupBox("Динамика денег, портфеля и общего капитала")
        capital_layout = QVBoxLayout(capital_box)
        capital_layout.addWidget(self.capital_canvas)
        allocation_box = QGroupBox("Структура текущего портфеля")
        allocation_layout = QVBoxLayout(allocation_box)
        allocation_layout.addWidget(self.allocation_canvas)
        charts_bottom.addWidget(capital_box, 3)
        charts_bottom.addWidget(allocation_box, 2)
        layout.addLayout(charts_bottom)

        pnl_box = QGroupBox("Инвестиционный результат")
        pnl_layout = QVBoxLayout(pnl_box)
        self.pnl_figure, self.pnl_axes, self.pnl_canvas = self._make_chart((9, 2.6))
        pnl_layout.addWidget(self.pnl_canvas)
        layout.addWidget(pnl_box)

        layout.addWidget(section("Сводка по типам операций"))
        self.breakdown = QTableWidget(0, 3)
        self.breakdown.setHorizontalHeaderLabels(["Тип операции", "Количество", "Денежный оборот"])
        configure_table(self.breakdown)
        layout.addWidget(wrap(self.breakdown))

        layout.addWidget(section("История операций за выбранный период"))
        self.history = QTableWidget(0, 5)
        self.history.setHorizontalHeaderLabels(["Дата", "Тип", "Категория", "Описание", "Сумма"])
        configure_table(self.history)
        layout.addWidget(wrap(self.history))

        note = QLabel(
            "Поступления и списания показывают фактическое движение денег: продажа актива считается поступлением на всю сумму, "
            "покупка — списанием на всю сумму. Реализованный P&L считается отдельно относительно себестоимости проданных позиций. "
            "Нереализованный P&L — текущая разница между стоимостью открытых позиций и их себестоимостью. "
            "Купонный доход показан отдельно и не включён в реализованный P&L. "
            "Текущие остатки и нереализованный результат не меняются при выборе исторического периода."
        )
        note.setWordWrap(True)
        note.setObjectName("Muted")
        layout.addWidget(note)

    def _make_chart(self, size):
        figure = Figure(figsize=size, dpi=90, facecolor=SURFACE)
        canvas = FigureCanvas(figure)
        canvas.setStyleSheet(f"background:{SURFACE};")
        axes = figure.add_subplot(111)
        return figure, axes, canvas

    def _period_start(self):
        days = self.period.currentData()
        if days == 0:
            return None
        with connect() as conn:
            today = simulated_datetime(conn).date()
        if days == -1:
            return date(today.year, 1, 1).isoformat()
        return (today - timedelta(days=days - 1)).isoformat()

    def _portfolio_data(self, conn):
        source_positions, cost, value = portfolio_totals(conn)
        # Остальная аналитика отчётов использует компактный формат из пяти полей.
        positions = [
            (name, quantity, average, current, kind)
            for name, _ticker, quantity, average, current, kind in source_positions
        ]
        return positions, cost, value

    def _draw_flow(self, operations):
        monthly = {}
        for op in operations:
            month = op["date"][:7]
            bucket = monthly.setdefault(month, [0, 0])
            if op["delta"] >= 0:
                bucket[0] += op["delta"]
            else:
                bucket[1] += -op["delta"]
        ax = self.flow_axes
        ax.clear()
        ax.set_facecolor(SURFACE)
        if not monthly:
            self._empty_chart(ax, self.flow_canvas, "Нет денежных операций за выбранный период")
            return
        months = sorted(monthly)
        incoming = [monthly[m][0] / 100 for m in months]
        outgoing = [monthly[m][1] / 100 for m in months]
        x = list(range(len(months)))
        width = 0.38
        ax.bar([v-width/2 for v in x], incoming, width, color=UP, label="Поступления")
        ax.bar([v+width/2 for v in x], outgoing, width, color=DOWN, label="Списания")
        ax.set_xticks(x)
        ax.set_xticklabels(months, rotation=30, ha="right", color=MUTED, fontsize=8)
        ax.legend(frameon=False, labelcolor=MUTED, fontsize=8)
        style_axes(ax)
        self.flow_figure.tight_layout()
        self.flow_canvas.draw_idle()

    def _draw_expenses(self, operations):
        categories = {}
        for op in operations:
            # Покупки ценных бумаг — инвестиционные операции, а не бытовые расходы.
            if op["delta"] < 0 and op["type"] in ("Расход", "Снятие"):
                key = op["category"] or "Без категории"
                categories[key] = categories.get(key, 0) - op["delta"]
        ax = self.expense_axes
        ax.clear()
        ax.set_facecolor(SURFACE)
        if not categories:
            self._empty_chart(ax, self.expense_canvas, "Нет расходов по категориям за период", axes_off=True)
            return
        ranked = sorted(categories.items(), key=lambda item: item[1], reverse=True)
        if len(ranked) > 7:
            ranked = ranked[:6] + [("Прочее", sum(v for _, v in ranked[6:]))]
        labels, values = zip(*ranked)
        wedges, _ = ax.pie(values, startangle=90, colors=PIE[:len(values)],
                           wedgeprops={"width": 0.42, "edgecolor": SURFACE, "linewidth": 2})
        ax.legend(wedges, labels, loc="center left", bbox_to_anchor=(0.98, 0.5),
                  frameon=False, fontsize=8, labelcolor=MUTED)
        ax.set_aspect("equal")
        self.expense_figure.tight_layout()
        self.expense_canvas.draw_idle()

    def _empty_chart(self, ax, canvas, message, axes_off=False):
        ax.clear()
        ax.set_facecolor(SURFACE)
        ax.text(0.5, 0.5, message, color=MUTED, ha="center", va="center", wrap=True,
                transform=ax.transAxes, fontsize=9)
        if axes_off:
            ax.axis("off")
        else:
            style_axes(ax)
            ax.set_xticks([])
            ax.set_yticks([])
        canvas.draw_idle()

    def _draw_capital(self, snapshots):
        ax = self.capital_axes
        ax.clear()
        ax.set_facecolor(SURFACE)
        if not snapshots:
            self._empty_chart(ax, self.capital_canvas, "История капитала начнёт формироваться по мере работы симулятора")
            return
        # Ограничиваем число точек только для отображения; исходные снимки в БД не меняются.
        rows = snapshots
        if len(rows) > 120:
            indexes = sorted({round(i * (len(rows)-1) / 119) for i in range(120)})
            rows = [rows[i] for i in indexes]
        x = list(range(len(rows)))
        cash = [r["cash_cents"] / 100 for r in rows]
        portfolio = [r["portfolio_value_cents"] / 100 for r in rows]
        net = [r["net_worth_cents"] / 100 for r in rows]
        ax.plot(x, cash, color=GOLD, linewidth=1.3, label="Деньги")
        ax.plot(x, portfolio, color=UP, linewidth=1.5, label="Портфель")
        ax.plot(x, net, color=ACCENT, linewidth=2, label="Общий капитал")
        step = max(1, len(rows)//8)
        labels = [datetime.fromisoformat(r["captured_at"]).strftime("%d.%m %H:%M")
                  if i % step == 0 or i == len(rows)-1 else "" for i, r in enumerate(rows)]
        ax.set_xticks(x)
        ax.set_xticklabels(labels, rotation=25, ha="right", color=MUTED, fontsize=7)
        ax.legend(frameon=False, labelcolor=MUTED, fontsize=8, ncol=3)
        style_axes(ax)
        self.capital_figure.tight_layout()
        self.capital_canvas.draw_idle()

    def _draw_allocation(self, positions):
        ax = self.allocation_axes
        ax.clear()
        ax.set_facecolor(SURFACE)
        buckets = {}
        for _, qty, _, current, kind in positions:
            amount = qty * current
            if amount > 0:
                buckets[kind] = buckets.get(kind, 0) + amount
        if not buckets:
            self._empty_chart(ax, self.allocation_canvas, "Портфель пока пуст", axes_off=True)
            return
        labels, values = zip(*sorted(buckets.items(), key=lambda item: item[1], reverse=True))
        wedges, _ = ax.pie(values, startangle=90, colors=PIE[:len(values)],
                           wedgeprops={"width": 0.42, "edgecolor": SURFACE, "linewidth": 2})
        ax.legend(wedges, labels, loc="center", bbox_to_anchor=(0.5, 0.5),
                  frameon=False, fontsize=8, labelcolor=MUTED)
        ax.set_aspect("equal")
        self.allocation_figure.tight_layout()
        self.allocation_canvas.draw_idle()

    def _draw_pnl(self, realized, unrealized, coupons):
        ax = self.pnl_axes
        ax.clear()
        ax.set_facecolor(SURFACE)
        values = [realized / 100, unrealized / 100, coupons / 100]
        labels = ["Реализованный · период", "Нереализованный · сейчас", "Купоны · период"]
        bars = ax.bar(range(3), values, color=[UP if v >= 0 else DOWN for v in values], width=0.48)
        ax.axhline(0, color=LINE, linewidth=0.8)
        ax.set_xticks(range(3))
        ax.set_xticklabels(labels, color=MUTED, fontsize=8)
        for bar, value in zip(bars, values):
            offset = 4 if value >= 0 else -12
            ax.annotate(f"{value:,.2f} ₽".replace(",", " "), (bar.get_x()+bar.get_width()/2, value),
                        xytext=(0, offset), textcoords="offset points", ha="center",
                        va="bottom" if value >= 0 else "top", color=TEXT, fontsize=8)
        style_axes(ax)
        ax.grid(False, axis="x")
        self.pnl_figure.tight_layout()
        self.pnl_canvas.draw_idle()

    def refresh(self):
        start = self._period_start()
        with connect() as conn:
            all_operations = operation_rows(conn)
            balance = cash_balance(conn)
            positions, portfolio_cost, portfolio_value = self._portfolio_data(conn)
            snapshots = conn.execute(
                "SELECT captured_at,cash_cents,portfolio_value_cents,net_worth_cents "
                "FROM financial_snapshots ORDER BY captured_at"
            ).fetchall()
            realized_sql = (
                "SELECT "
                "COALESCE((SELECT SUM(realized_pnl_cents) FROM trades WHERE (? IS NULL OR trade_date >= ?)),0) + "
                "COALESCE((SELECT SUM(realized_pnl_cents) FROM bond_trades WHERE (? IS NULL OR trade_date >= ?)),0) + "
                "COALESCE((SELECT SUM(realized_pnl_cents) FROM bond_redemptions WHERE (? IS NULL OR payment_date >= ?)),0)"
            )
            realized = int(conn.execute(realized_sql, (start, start, start, start, start, start)).fetchone()[0] or 0)

        operations = [row for row in all_operations if start is None or row["date"][:10] >= start]
        coupon_income = sum(row["delta"] for row in operations if row["type"] == "Выплата купона")
        inflows = sum(row["delta"] for row in operations if row["delta"] > 0)
        outflows = -sum(row["delta"] for row in operations if row["delta"] < 0)
        net_flow = inflows - outflows
        purchases = -sum(row["delta"] for row in operations
                         if row["delta"] < 0 and row["type"] in ("Покупка акций", "Покупка облигаций"))
        unrealized = portfolio_value - portfolio_cost

        self.income_metric.value_label.setText(money(inflows))
        self.expense_metric.value_label.setText(money(outflows))
        self.net_metric.value_label.setText(("+" if net_flow > 0 else "") + money(net_flow))
        self.balance_metric.value_label.setText(money(balance))
        self.buy_metric.value_label.setText(money(purchases))
        self.value_metric.value_label.setText(money(portfolio_value))
        self.unrealized_metric.value_label.setText(("+" if unrealized > 0 else "") + money(unrealized))
        self.realized_metric.value_label.setText(("+" if realized > 0 else "") + money(realized))
        self.coupon_metric.value_label.setText(("+" if coupon_income > 0 else "") + money(coupon_income))

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
            for c, value in enumerate((row["date"], row["type"], row["category"],
                                       row["description"], row["amount"])):
                put(self.history, r, c, value)

        filtered_snapshots = [row for row in snapshots
                              if start is None or row["captured_at"][:10] >= start]
        self._draw_flow(operations)
        self._draw_expenses(operations)
        self._draw_capital(filtered_snapshots)
        self._draw_allocation(positions)
        self._draw_pnl(realized, unrealized, coupon_income)


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

        history_controls = QHBoxLayout()
        self.selected_stock = QLabel("Акция не выбрана")
        self.history_toggle = QPushButton("История цены")
        self.history_toggle.setEnabled(False)
        self.history_toggle.clicked.connect(self.toggle_price_history)
        history_controls.addWidget(self.selected_stock)
        history_controls.addStretch()
        history_controls.addWidget(self.history_toggle)
        layout.addLayout(history_controls)

        history_box = QGroupBox("История цены выбранной акции")
        self.history_box = history_box
        history_box.setVisible(False)
        history_layout = QVBoxLayout(history_box)
        controls = QHBoxLayout()
        controls.addWidget(QLabel("Период:"))
        self.history_period = QComboBox()
        self.history_period.addItem("Последние 10 дней", 10)
        self.history_period.addItem("Последние 30 дней", 30)
        self.history_period.addItem("Последние 90 дней", 90)
        controls.addWidget(self.history_period)
        controls.addSpacing(16)
        controls.addWidget(QLabel("Детальность:"))
        self.history_detail = QComboBox()
        self.history_detail.addItem("10 изменений за период", "summary")
        self.history_detail.addItem("Каждый час", "hourly")
        controls.addWidget(self.history_detail)
        controls.addStretch()
        history_layout.addLayout(controls)
        self.history_figure = Figure(figsize=(9, 3), dpi=90, facecolor=SURFACE)
        self.history_canvas = FigureCanvas(self.history_figure)
        self.history_axes = self.history_figure.add_subplot(111)
        history_layout.addWidget(self.history_canvas)
        self.price_history = QTableWidget(0, 5)
        self.price_history.setHorizontalHeaderLabels(["Симулируемое время", "Цена", "Изменение", "Изменение, %", "Описание"])
        configure_table(self.price_history)
        history_layout.addWidget(wrap(self.price_history))
        self.history_period.currentIndexChanged.connect(self.refresh_price_history)
        self.history_detail.currentIndexChanged.connect(self.refresh_price_history)
        layout.addWidget(history_box, 3)

        trade_box = QGroupBox("Совершить сделку")
        trade_form = QHBoxLayout(trade_box)
        self.selected_stock_trade = QLabel("Выбери акцию в таблице выше")
        self.selected_stock_trade.setMinimumWidth(170)
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
        trade_form.addWidget(self.selected_stock_trade, 2)
        trade_form.addWidget(QLabel("Количество:"))        trade_form.addWidget(self.quantity)
        trade_form.addWidget(buy)
        trade_form.addWidget(sell)
        layout.addWidget(trade_box)

        layout.addWidget(section("Мои акции"))
        self.holdings_table = QTableWidget(0, 7)
        self.holdings_table.setHorizontalHeaderLabels(["Тикер", "Компания", "Количество", "Средняя покупка", "Текущая стоимость", "Прибыль / убыток", "Прибыль / убыток, %"])
        configure_table(self.holdings_table)
        layout.addWidget(wrap(self.holdings_table), 2)

        self.selected_ticker = None

    def cash_balance(self, conn):
        return cash_balance(conn)

    def refresh(self):
        with connect() as conn:
            stocks = conn.execute("SELECT * FROM stocks ORDER BY ticker").fetchall()
            cash = self.cash_balance(conn)
            holdings = conn.execute("SELECT h.*, s.name, s.price_cents FROM holdings h JOIN stocks s ON s.ticker=h.ticker WHERE h.quantity > 0 ORDER BY h.ticker").fetchall()
        self.cash_label.setText(f"Доступно: {money(cash)}")
        self.portfolio_label.setText(f"Стоимость акций: {money(sum(int(round(h['quantity'] * h['price_cents'])) for h in holdings))}")
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
            current_value = int(round(h["quantity"] * h["price_cents"]))
            cost_value = int(round(h["quantity"] * h["average_price_cents"]))
            pnl = current_value - cost_value
            pnl_pct = (pnl / cost_value * 100) if cost_value else 0.0
            vals = [h["ticker"], h["name"], f"{h['quantity']:.2f}",
                    money(h["average_price_cents"]), money(current_value),
                    ("+" if pnl > 0 else "") + money(pnl), f"{pnl_pct:+.2f}%"]
            for c, value in enumerate(vals):
                put(self.holdings_table, r, c, value)
        self.update_selected_price()
        if not self.history_box.isHidden():
            self.refresh_price_history()

    def update_selected_price(self):
        row = self.market.currentRow()
        if row < 0:
            self.selected_ticker = None
            self.selected_stock.setText("Акция не выбрана")
            self.selected_stock_trade.setText("Выбери акцию в таблице выше")
            self.history_toggle.setEnabled(False)
            return
        item = self.market.item(row, 0)
        if item:
            self.selected_ticker = item.text()
            self.selected_stock.setText(f"Выбрана акция: {self.selected_ticker}")
            self.selected_stock_trade.setText(f"Выбрано: {self.selected_ticker}")
            self.history_toggle.setEnabled(True)
            if not self.history_box.isHidden():
                self.refresh_price_history()

    def toggle_price_history(self):
        visible = self.history_box.isHidden()
        self.history_box.setVisible(visible)
        self.history_toggle.setText("Скрыть историю" if visible else "История цены")
        if visible:
            self.refresh_price_history()

    def move_market(self):
        # Один тик таймера равен одному часу симулируемого биржевого времени.
        with connect() as conn:
            clock = conn.execute("SELECT simulated_at FROM market_clock WHERE id=1").fetchone()
            market_time = datetime.fromisoformat(clock["simulated_at"]) + timedelta(hours=1)
            stamp = market_time.isoformat(timespec="seconds")
            conn.execute("UPDATE market_clock SET simulated_at=? WHERE id=1", (stamp,))
            rows = conn.execute("SELECT ticker, price_cents, volatility FROM stocks").fetchall()
            for stock in rows:
                new_price = monte_carlo_price_step(
                    stock["price_cents"],
                    stock["volatility"],
                    annual_return_percent=8.0,
                )
                conn.execute(
                    "UPDATE stocks SET previous_price_cents=price_cents, "
                    "price_cents=?, updated_at=? WHERE ticker=?",
                    (new_price, stamp, stock["ticker"]),
                )
                conn.execute(
                    "INSERT OR IGNORE INTO stock_price_history(ticker,simulated_at,price_cents) VALUES(?,?,?)",
                    (stock["ticker"], stamp, new_price),
                )
            record_financial_snapshot(conn)
        self.refresh()

    def refresh_price_history(self):
        ticker = self.selected_ticker
        self.history_axes.clear()
        self.price_history.setRowCount(0)
        if not ticker:
            self.history_axes.text(0.5,0.5,"Выбери акцию, чтобы увидеть историю цены",
                                   ha="center",va="center",transform=self.history_axes.transAxes,color=MUTED)
            style_axes(self.history_axes)
            self.history_canvas.draw_idle()
            return
        days = int(self.history_period.currentData() or 10)
        with connect() as conn:
            clock = conn.execute("SELECT simulated_at FROM market_clock WHERE id=1").fetchone()
            now = datetime.fromisoformat(clock["simulated_at"]) if clock else datetime.now()
            start = (now - timedelta(days=days)).isoformat(timespec="seconds")
            rows = conn.execute(
                """SELECT simulated_at,price_cents FROM stock_price_history
                   WHERE ticker=? AND simulated_at>=? ORDER BY simulated_at""",
                (ticker,start)
            ).fetchall()
        data = list(rows)
        if not data:
            self.history_axes.text(0.5,0.5,"История начнёт собираться после обновлений котировок",
                                   ha="center",va="center",transform=self.history_axes.transAxes,color=MUTED)
            style_axes(self.history_axes)
            self.history_canvas.draw_idle()
            return
        if self.history_detail.currentData()=="summary" and len(data)>10:
            indices = sorted({round(i*(len(data)-1)/9) for i in range(10)})
            shown = [data[i] for i in indices]
        else:
            shown = data
        times = [datetime.fromisoformat(row["simulated_at"]) for row in shown]
        prices = [row["price_cents"]/100 for row in shown]
        self.history_axes.plot(times,prices,linewidth=1.8,marker="o" if len(times)<=20 else None,
                               markersize=3,color=ACCENT)
        self.history_axes.set_ylabel("Цена, ₽",color=MUTED)
        self.history_axes.tick_params(axis="x",labelrotation=30,labelcolor=MUTED)
        self.history_axes.tick_params(axis="y",labelcolor=MUTED)
        style_axes(self.history_axes)
        self.history_figure.tight_layout()
        self.history_canvas.draw_idle()
        self.price_history.setRowCount(len(shown))
        previous=None
        for i,row in enumerate(shown):
            price=int(row["price_cents"])
            if previous is None:
                change_text = pct_text = direction = "—"
                change_color = None
            else:
                change=price-previous
                pct=(change/previous*100) if previous else 0
                direction="Рост" if change>0 else ("Падение" if change<0 else "Без изменения")
                change_text=("+" if change>0 else "")+money(change)
                pct_text=f"{pct:+.2f}%"
                change_color=UP if change>0 else DOWN if change<0 else None
            vals=[datetime.fromisoformat(row["simulated_at"]).strftime("%d.%m.%Y %H:%M"),
                  money(price),change_text,pct_text,direction]
            for col,value in enumerate(vals):
                put(self.price_history,i,col,value,change_color if col in (2,3,4) else None)
            previous=price

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
                    (simulated_datetime(conn).isoformat(timespec="seconds"), ticker, side, quantity, price, total, realized_pnl)
                )
                record_financial_snapshot(conn)
            action = "Куплено" if side == "BUY" else "Продано"
            QMessageBox.information(self, "Сделка выполнена", f"{action} {quantity:.2f} акций {ticker} по {money(price)} за штуку.\nСумма: {money(total)}.")
            self.refresh()
        except Exception as exc:
            QMessageBox.warning(self, "Не удалось совершить сделку", str(exc))