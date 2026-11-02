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
            total_cents INTEGER NOT NULL CHECK(total_cents > 0)
        );
        """)
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
