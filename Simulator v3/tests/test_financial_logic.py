import sqlite3
import unittest

from database import cash_balance, portfolio_totals


class FinancialLogicTests(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript("""
            CREATE TABLE transactions(tx_type TEXT, amount_cents INTEGER);
            CREATE TABLE trades(side TEXT, total_cents INTEGER);
            CREATE TABLE bond_trades(side TEXT, total_cents INTEGER);
            CREATE TABLE bond_coupon_payments(amount_cents INTEGER);
            CREATE TABLE bond_redemptions(amount_cents INTEGER);

            CREATE TABLE assets(
                name TEXT, ticker TEXT, quantity REAL,
                average_price_cents INTEGER, current_price_cents INTEGER
            );
            CREATE TABLE stocks(ticker TEXT, name TEXT, price_cents INTEGER);
            CREATE TABLE holdings(ticker TEXT, quantity REAL, average_price_cents INTEGER);
            CREATE TABLE bonds(ticker TEXT, name TEXT, price_cents INTEGER);
            CREATE TABLE bond_holdings(ticker TEXT, quantity REAL, average_price_cents INTEGER);
        """)

    def tearDown(self):
        self.conn.close()

    def test_cash_balance_combines_all_ledger_sources(self):
        self.conn.executemany(
            "INSERT INTO transactions(tx_type,amount_cents) VALUES(?,?)",
            [("Income", 1_000_000), ("Deposit", 20_000), ("Expense", 5_000)],
        )
        self.conn.executemany(
            "INSERT INTO trades(side,total_cents) VALUES(?,?)",
            [("BUY", 10_000), ("SELL", 12_000)],
        )
        self.conn.executemany(
            "INSERT INTO bond_trades(side,total_cents) VALUES(?,?)",
            [("BUY", 30_000), ("SELL", 31_000)],
        )
        self.conn.execute("INSERT INTO bond_coupon_payments VALUES(1000)")
        self.conn.execute("INSERT INTO bond_redemptions VALUES(100000)")

        self.assertEqual(cash_balance(self.conn), 1_119_000)

    def test_portfolio_values_market_positions_once(self):
        self.conn.executemany(
            "INSERT INTO assets VALUES(?,?,?,?,?)",
            [
                ("Manual Apple", "AAPL", 2, 100, 110),
                ("Manual bond", "OFZ-TEST", 4, 90, 95),
                ("Gold", "", 1, 400, 500),
            ],
        )
        self.conn.execute("INSERT INTO stocks VALUES('AAPL','Apple',250)")
        self.conn.execute("INSERT INTO holdings VALUES('AAPL',1,200)")
        self.conn.execute("INSERT INTO bonds VALUES('OFZ-TEST','Test OFZ',105)")
        self.conn.execute("INSERT INTO bond_holdings VALUES('OFZ-TEST',3,100)")

        positions, cost, value = portfolio_totals(self.conn)

        self.assertEqual(len(positions), 3)
        self.assertEqual(cost, 900)
        self.assertEqual(value, 1_065)
        self.assertEqual(
            {position[1] for position in positions},
            {"", "AAPL", "OFZ-TEST"},
        )


if __name__ == "__main__":
    unittest.main()


class FinanceInputTests(unittest.TestCase):
    def test_compound_interest_handles_large_supported_values(self):
        from finance import compound_interest

        result = compound_interest(100_000_000, 100, 50, 1)
        self.assertEqual(result, 100_000_000 * (2 ** 50))

    def test_projected_value_rejects_rate_below_minus_100_percent(self):
        from finance import projected_value

        with self.assertRaisesRegex(ValueError, "-100"):
            projected_value(1_000_000, -150, 1)

    def test_projected_value_allows_minus_100_percent(self):
        from finance import projected_value

        self.assertEqual(projected_value(1_000_000, -100, 1), 0)
        self.assertEqual(projected_value(1_000_000, -100, 0), 1_000_000)

    def test_to_cents_reports_invalid_input_as_value_error(self):
        from finance import to_cents

        for value in ("abc", "NaN", "Infinity"):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    to_cents(value)


if __name__ == "__main__":
    unittest.main()
