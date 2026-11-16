import sqlite3
from pathlib import Path
from datetime import date

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
        conn.executemany("INSERT OR IGNORE INTO stocks(ticker,name,price_cents,previous_price_cents,volatility) VALUES(?,?,?,?,?)", stocks)
        conn.execute("INSERT OR IGNORE INTO holdings(ticker, quantity, average_price_cents) SELECT ticker, 0, 0 FROM stocks")
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
    cash = int(income - expense + trade_cash)

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
    portfolio_cost = int(manual["cost"] + market["cost"])
    portfolio_value = int(manual["value"] + market["value"])
    captured_at = datetime.now().isoformat(timespec="microseconds")
    conn.execute(
        """INSERT INTO financial_snapshots(
               captured_at,cash_cents,portfolio_cost_cents,portfolio_value_cents,net_worth_cents
           ) VALUES(?,?,?,?,?)""",
        (captured_at, cash, portfolio_cost, portfolio_value, cash + portfolio_value),
    )
