import sqlite3
from pathlib import Path
from datetime import date
import calendar


def add_months(value, months):
    month_index = value.month - 1 + months
    year = value.year + month_index // 12
    month = month_index % 12 + 1
    day = min(value.day, calendar.monthrange(year, month)[1])
    return value.replace(year=year, month=month, day=day)

DB_PATH = Path(__file__).parent / "data" / "ledger.sqlite3"

def connect():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn

def init_db():
    with connect() as conn:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tx_date TEXT NOT NULL,
            tx_type TEXT NOT NULL CHECK(tx_type IN ('Income','Expense','Deposit','Withdrawal')),
            category TEXT NOT NULL,
            description TEXT DEFAULT '',
            amount_cents INTEGER NOT NULL CHECK(amount_cents > 0)
        );
        CREATE TABLE IF NOT EXISTS assets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            ticker TEXT DEFAULT '',
            quantity REAL NOT NULL DEFAULT 0 CHECK(quantity >= 0),
            average_price_cents INTEGER NOT NULL DEFAULT 0 CHECK(average_price_cents >= 0),
            current_price_cents INTEGER NOT NULL DEFAULT 0 CHECK(current_price_cents >= 0)
        );
        CREATE TABLE IF NOT EXISTS deposit_scenarios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            principal_cents INTEGER NOT NULL,
            annual_rate REAL NOT NULL,
            years REAL NOT NULL,
            compounds_per_year INTEGER NOT NULL,
            result_cents INTEGER NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS simulation_runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            initial_cents INTEGER NOT NULL,
            annual_rate REAL NOT NULL,
            years INTEGER NOT NULL,
            final_cents INTEGER NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS market_clock (
            id INTEGER PRIMARY KEY CHECK(id=1),
            simulated_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS stock_price_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ticker TEXT NOT NULL REFERENCES stocks(ticker),
            simulated_at TEXT NOT NULL,
            price_cents INTEGER NOT NULL CHECK(price_cents>0),
            UNIQUE(ticker, simulated_at)
        );
        CREATE INDEX IF NOT EXISTS idx_stock_history_ticker_time
            ON stock_price_history(ticker, simulated_at);
        CREATE TABLE IF NOT EXISTS stocks (
            ticker TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            price_cents INTEGER NOT NULL CHECK(price_cents > 0),
            previous_price_cents INTEGER NOT NULL CHECK(previous_price_cents > 0),
            volatility REAL NOT NULL DEFAULT 0.008,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS holdings (
            ticker TEXT PRIMARY KEY REFERENCES stocks(ticker),
            quantity REAL NOT NULL DEFAULT 0 CHECK(quantity >= 0),
            average_price_cents INTEGER NOT NULL DEFAULT 0 CHECK(average_price_cents >= 0)
        );
        CREATE TABLE IF NOT EXISTS trades (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            trade_date TEXT NOT NULL,
            ticker TEXT NOT NULL REFERENCES stocks(ticker),
            side TEXT NOT NULL CHECK(side IN ('BUY','SELL')),
            quantity REAL NOT NULL CHECK(quantity > 0),
            price_cents INTEGER NOT NULL CHECK(price_cents > 0),
            total_cents INTEGER NOT NULL CHECK(total_cents > 0),
            realized_pnl_cents INTEGER NOT NULL DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS bonds (
            ticker TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            issuer_type TEXT NOT NULL CHECK(issuer_type IN ('Государственная','Корпоративная')),
            face_value_cents INTEGER NOT NULL CHECK(face_value_cents > 0),
            price_cents INTEGER NOT NULL CHECK(price_cents > 0),
            previous_price_cents INTEGER NOT NULL CHECK(previous_price_cents > 0),
            coupon_rate REAL NOT NULL CHECK(coupon_rate >= 0),
            maturity_date TEXT NOT NULL,
            next_coupon_date TEXT NOT NULL,
            volatility REAL NOT NULL DEFAULT 0.001
        );
        CREATE TABLE IF NOT EXISTS bond_holdings (
            ticker TEXT PRIMARY KEY REFERENCES bonds(ticker),
            quantity REAL NOT NULL DEFAULT 0 CHECK(quantity >= 0),
            average_price_cents INTEGER NOT NULL DEFAULT 0 CHECK(average_price_cents >= 0)
        );
        CREATE TABLE IF NOT EXISTS bond_trades (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            trade_date TEXT NOT NULL,
            ticker TEXT NOT NULL REFERENCES bonds(ticker),
            side TEXT NOT NULL CHECK(side IN ('BUY','SELL')),
            quantity REAL NOT NULL CHECK(quantity > 0),
            price_cents INTEGER NOT NULL CHECK(price_cents > 0),
            total_cents INTEGER NOT NULL CHECK(total_cents > 0)
        );
        CREATE TABLE IF NOT EXISTS bond_coupon_payments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            payment_date TEXT NOT NULL,
            ticker TEXT NOT NULL REFERENCES bonds(ticker),
            quantity REAL NOT NULL,
            amount_cents INTEGER NOT NULL
        );
        CREATE TABLE IF NOT EXISTS bond_redemptions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            payment_date TEXT NOT NULL,
            ticker TEXT NOT NULL REFERENCES bonds(ticker),
            quantity REAL NOT NULL,
            amount_cents INTEGER NOT NULL
        );
        CREATE TABLE IF NOT EXISTS financial_snapshots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            captured_at TEXT NOT NULL,
            cash_cents INTEGER NOT NULL,
            portfolio_cost_cents INTEGER NOT NULL,
            portfolio_value_cents INTEGER NOT NULL,
            net_worth_cents INTEGER NOT NULL
        );
        """)
        trade_columns = {row["name"] for row in conn.execute("PRAGMA table_info(trades)")}
        if "realized_pnl_cents" not in trade_columns:
            conn.execute("ALTER TABLE trades ADD COLUMN realized_pnl_cents INTEGER NOT NULL DEFAULT 0")
            # Восстанавливаем историческую реализованную прибыль для старых сделок
            # по методу средневзвешенной себестоимости.
            positions = {}
            legacy_trades = conn.execute(
                "SELECT id,ticker,side,quantity,price_cents FROM trades ORDER BY trade_date,id"
            ).fetchall()
            for trade in legacy_trades:
                qty, average = positions.get(trade["ticker"], (0.0, 0.0))
                if trade["side"] == "BUY":
                    new_qty = qty + trade["quantity"]
                    new_average = (
                        (qty * average + trade["quantity"] * trade["price_cents"]) / new_qty
                        if new_qty else 0.0
                    )
                    positions[trade["ticker"]] = (new_qty, new_average)
                else:
                    realized = int(round(trade["quantity"] * (trade["price_cents"] - average)))
                    conn.execute(
                        "UPDATE trades SET realized_pnl_cents=? WHERE id=?",
                        (realized, trade["id"])
                    )
                    positions[trade["ticker"]] = (max(0.0, qty - trade["quantity"]), average)

        stocks = [
            ("AAPL", "Apple Inc.", 23_000, 23_000, 0.010),
            ("MSFT", "Microsoft Corp.", 42_000, 42_000, 0.009),
            ("NVDA", "NVIDIA Corp.", 18_000, 18_000, 0.020),
            ("AMZN", "Amazon.com Inc.", 22_000, 22_000, 0.013),
            ("GOOGL", "Alphabet Inc.", 17_000, 17_000, 0.012),
            ("META", "Meta Platforms Inc.", 30_000, 30_000, 0.016),
            ("TSLA", "Tesla Inc.", 25_000, 25_000, 0.022),
            ("NFLX", "Netflix Inc.", 95_000, 95_000, 0.018),
        ]
        stocks.extend([
            ("ORCL","Oracle Corporation",19_500,19_500,0.012),
            ("IBM","IBM",21_000,21_000,0.010),
            ("INTC","Intel Corporation",4_300,4_300,0.018),
            ("AMD","Advanced Micro Devices",14_000,14_000,0.020),
            ("QCOM","Qualcomm",16_500,16_500,0.014),
            ("ADBE","Adobe Inc.",52_000,52_000,0.016),
            ("CRM","Salesforce",28_000,28_000,0.015),
            ("UBER","Uber Technologies",7_500,7_500,0.019),
            ("DIS","The Walt Disney Company",9_000,9_000,0.014),
            ("KO","Coca-Cola",6_200,6_200,0.007),
            ("PEP","PepsiCo",17_000,17_000,0.008),
            ("WMT","Walmart",9_500,9_500,0.009),
            ("COST","Costco",85_000,85_000,0.010),
            ("JPM","JPMorgan Chase",24_000,24_000,0.012),
            ("BAC","Bank of America",4_000,4_000,0.014),
            ("V","Visa",31_000,31_000,0.011),
            ("MA","Mastercard",48_000,48_000,0.011),
            ("NKE","Nike",7_000,7_000,0.014),
            ("SONY","Sony Group",8_500,8_500,0.013),
            ("SAP","SAP SE",23_000,23_000,0.012),
            ("BABA","Alibaba Group",8_000,8_000,0.019),
            ("SHOP","Shopify",10_500,10_500,0.022),
            ("PYPL","PayPal",6_500,6_500,0.018),
            ("CSCO","Cisco Systems",6_000,6_000,0.010),
        ])
        conn.executemany("INSERT OR IGNORE INTO stocks(ticker,name,price_cents,previous_price_cents,volatility) VALUES(?,?,?,?,?)", stocks)
        from datetime import datetime
        market_now = datetime.now().replace(minute=0, second=0, microsecond=0).isoformat(timespec="seconds")
        conn.execute("INSERT OR IGNORE INTO market_clock(id,simulated_at) VALUES(1,?)", (market_now,))
        conn.execute("""
            INSERT OR IGNORE INTO stock_price_history(ticker,simulated_at,price_cents)
            SELECT ticker, ?, price_cents FROM stocks
        """, (market_now,))

        conn.execute("INSERT OR IGNORE INTO holdings(ticker, quantity, average_price_cents) SELECT ticker, 0, 0 FROM stocks")
        from datetime import date
        bond_rows = [
            ("OFZ-26238","ОФЗ 26238","Государственная",100_000,98_500,98_500,7.1,5,0.0010),
            ("OFZ-26240","ОФЗ 26240","Государственная",100_000,96_800,96_800,7.0,7,0.0012),
            ("OFZ-26242","ОФЗ 26242","Государственная",100_000,101_200,101_200,8.0,4,0.0010),
            ("OFZ-29025","ОФЗ 29025","Государственная",100_000,99_400,99_400,6.5,3,0.0008),
            ("CORP-GAZP","Газпром БО-001Р","Корпоративная",1_000,1_012,1_012,9.2,3,0.0020),
            ("CORP-ROSN","Роснефть 001Р","Корпоративная",1_000,995,995,8.7,4,0.0020),
            ("CORP-RZD","РЖД 001Р","Корпоративная",1_000,1_018,1_018,8.4,5,0.0015),
            ("CORP-SBER","Сбербанк 001Р","Корпоративная",1_000,1_006,1_006,8.9,3,0.0018),
            ("CORP-MTS","МТС 001Р","Корпоративная",1_000,987,987,10.1,2,0.0025),
            ("CORP-YNDX","Яндекс 001Р","Корпоративная",1_000,1_004,1_004,9.6,4,0.0024),
        ]
        today = date.today()
        for ticker,name,kind,face,price,prev,coupon,term,vol in bond_rows:
            maturity = add_months(today, term * 12)
            next_coupon = add_months(today, 6)
            conn.execute(
                """INSERT OR IGNORE INTO bonds(
                    ticker,name,issuer_type,face_value_cents,price_cents,previous_price_cents,
                    coupon_rate,maturity_date,next_coupon_date,volatility
                ) VALUES(?,?,?,?,?,?,?,?,?,?)""",
                (ticker,name,kind,face,price,prev,coupon,maturity.isoformat(),next_coupon.isoformat(),vol)
            )
            conn.execute("INSERT OR IGNORE INTO bond_holdings(ticker,quantity,average_price_cents) VALUES(?,0,0)",(ticker,))

        has_any = conn.execute("SELECT EXISTS(SELECT 1 FROM transactions) OR EXISTS(SELECT 1 FROM trades)").fetchone()[0]
        if not has_any:
            conn.execute("INSERT INTO transactions(tx_date,tx_type,category,description,amount_cents) VALUES(?,?,?,?,?)",
                         (date.today().isoformat(), "Income", "Стартовый капитал", "Начальный баланс для демонстрации торговли", 1_000_000))
        record_financial_snapshot(conn)


def record_financial_snapshot(conn):
    """Сохранить согласованный снимок денежных средств и рыночной стоимости активов."""
    from datetime import datetime

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
    redemptions = conn.execute("SELECT COALESCE(SUM(amount_cents),0) FROM bond_redemptions").fetchone()[0]
    cash = int(income - expense + trade_cash + bond_trade_cash + coupons + redemptions)

    manual = conn.execute("""
        SELECT COALESCE(SUM(CAST(ROUND(a.quantity * a.average_price_cents) AS INTEGER)),0) AS cost,
               COALESCE(SUM(CAST(ROUND(a.quantity * a.current_price_cents) AS INTEGER)),0) AS value
        FROM assets a
        WHERE NOT EXISTS (
            SELECT 1 FROM holdings h
            WHERE h.ticker = UPPER(a.ticker) AND h.quantity > 0
        )
    """).fetchone()
    market = conn.execute("""
        SELECT COALESCE(SUM(CAST(ROUND(h.quantity * h.average_price_cents) AS INTEGER)),0) AS cost,
               COALESCE(SUM(CAST(ROUND(h.quantity * s.price_cents) AS INTEGER)),0) AS value
        FROM holdings h JOIN stocks s ON s.ticker=h.ticker
        WHERE h.quantity > 0
    """).fetchone()
    bonds_value = conn.execute("""
        SELECT COALESCE(SUM(CAST(ROUND(h.quantity*b.price_cents) AS INTEGER)),0)
        FROM bond_holdings h JOIN bonds b ON b.ticker=h.ticker WHERE h.quantity>0
    """).fetchone()[0]
    bonds_cost = conn.execute("""
        SELECT COALESCE(SUM(CAST(ROUND(h.quantity*h.average_price_cents) AS INTEGER)),0)
        FROM bond_holdings h WHERE h.quantity>0
    """).fetchone()[0]
    portfolio_cost = int(manual["cost"] + market["cost"] + bonds_cost)
    portfolio_value = int(manual["value"] + market["value"] + bonds_value)
    captured_at = datetime.now().isoformat(timespec="microseconds")
    conn.execute(
        """INSERT INTO financial_snapshots(
               captured_at,cash_cents,portfolio_cost_cents,portfolio_value_cents,net_worth_cents
           ) VALUES(?,?,?,?,?)""",
        (captured_at, cash, portfolio_cost, portfolio_value, cash + portfolio_value),
    )
