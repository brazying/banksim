"""Сценарные тесты интерфейса: сделки, облигации, вклады, моделирование.

Запускаются без экрана (Qt offscreen) на временной базе данных.
"""
import os
import tempfile
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import database  # noqa: E402
from PyQt6.QtWidgets import QApplication, QMessageBox  # noqa: E402

_app = QApplication.instance() or QApplication([])


class AppFlowTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self._old_path = database.DB_PATH
        database.DB_PATH = Path(self._tmp.name) / "test.sqlite3"
        database.init_db()

        self.dialogs = []
        self._old_dialogs = {}
        for name in ("warning", "information", "critical"):
            self._old_dialogs[name] = getattr(QMessageBox, name)
            setattr(QMessageBox, name, staticmethod(
                lambda *a, _n=name, **k: self.dialogs.append((_n, a[1:3]))))

        import main
        self.window = main.MainWindow()
        self.pages = self.window.page_widgets
        self.stocks = self.window.stock_market_page
        self.bonds = self.window.bonds_page

    def tearDown(self):
        for name, fn in self._old_dialogs.items():
            setattr(QMessageBox, name, fn)
        database.DB_PATH = self._old_path
        self.window.close()
        self._tmp.cleanup()

    # --- вспомогательные функции
    def cash(self):
        with database.connect() as conn:
            return database.cash_balance(conn)

    def one(self, sql, *args):
        with database.connect() as conn:
            return conn.execute(sql, args).fetchone()

    def select_stock(self, ticker):
        self.stocks.refresh()
        table = self.stocks.market
        for row in range(table.rowCount()):
            if table.item(row, 0).text() == ticker:
                table.selectRow(row)
                return
        self.fail(f"{ticker} не найден в таблице котировок")

    def select_holding(self, ticker):
        self.stocks.refresh()
        table = self.stocks.holdings_table
        for row in range(table.rowCount()):
            item = table.item(row, 0)
            if item and item.text() == ticker:
                table.selectRow(row)
                return
        self.fail(f"{ticker} не найден в «Мои акции»")

    # --- навигация
    def test_every_page_opens(self):
        for index in range(len(self.window.nav_buttons)):
            self.window.navigate(index)
        for tab in range(self.window.exchange_page.tabs.count()):
            self.window.exchange_page.tabs.setCurrentIndex(tab)

    def test_market_advances_without_errors(self):
        for _ in range(20):
            self.window.advance_market_hour()
        self.assertFalse(self.one("SELECT 1 FROM stocks WHERE price_cents <= 0"))
        self.assertFalse(self.one("SELECT 1 FROM bonds WHERE price_cents <= 0"))

    # --- акции
    def test_stock_buy_and_sell(self):
        start = self.cash()
        price = self.one("SELECT price_cents FROM stocks WHERE ticker='AAPL'")[0]
        self.select_stock("AAPL")
        self.stocks.quantity.setValue(2)
        self.stocks.execute_trade("BUY")
        self.assertEqual(self.cash(), start - round(price * 2))

        self.select_holding("AAPL")
        self.stocks.sell_quantity.setValue(1)
        self.stocks.execute_trade("SELL")
        self.assertEqual(self.one("SELECT quantity FROM holdings WHERE ticker='AAPL'")[0], 1)

    def test_stock_oversell_and_overbuy_are_rejected(self):
        self.select_stock("AAPL")
        self.stocks.quantity.setValue(1)
        self.stocks.execute_trade("BUY")
        self.select_holding("AAPL")
        self.stocks.sell_quantity.setValue(5)
        before = self.cash()
        self.dialogs.clear()
        self.stocks.execute_trade("SELL")
        self.assertEqual(self.dialogs[-1][0], "warning")
        self.assertEqual(self.cash(), before)

        self.select_stock("AAPL")
        self.stocks.quantity.setValue(self.stocks.quantity.maximum())
        self.dialogs.clear()
        self.stocks.execute_trade("BUY")
        self.assertEqual(self.dialogs[-1][0], "warning")
        self.assertEqual(self.cash(), before)

    def test_trade_without_selection_is_rejected(self):
        self.dialogs.clear()
        self.stocks.execute_trade("BUY")
        self.stocks.execute_trade("SELL")
        self.assertEqual([d[0] for d in self.dialogs], ["warning", "warning"])

    # --- банковский счёт
    def test_account_validation(self):
        account = self.pages[1]
        balance = self.cash()
        account.category.setText("Тест")
        account.kind.setCurrentIndex(account.kind.findData("Expense"))
        account.amount.setValue(balance / 100 + 1)
        self.dialogs.clear()
        account.add_transaction()
        self.assertEqual(self.cash(), balance)
        self.assertEqual(self.dialogs[-1][0], "warning")

        account.category.setText("   ")
        account.amount.setValue(1)
        self.dialogs.clear()
        account.add_transaction()
        self.assertEqual(self.cash(), balance)
        self.assertEqual(self.dialogs[-1][0], "warning")

    # --- облигации
    def test_bond_buy_sell_coupons_and_redemption(self):
        self.bonds.selected_ticker = "OFZ-26238"
        price = self.one("SELECT price_cents FROM bonds WHERE ticker='OFZ-26238'")[0]
        before = self.cash()
        self.bonds.quantity.setValue(3)
        self.bonds.execute_trade("BUY")
        self.assertEqual(self.cash(), before - 3 * price)

        self.bonds.quantity.setValue(10)
        self.dialogs.clear()
        self.bonds.execute_trade("SELL")
        self.assertEqual(self.dialogs[-1][0], "warning")

        with database.connect() as conn:
            conn.execute("UPDATE market_clock SET simulated_at='2035-01-01T00:00:00'")
            self.bonds.process_coupon_payments(conn)
            coupons = conn.execute("SELECT COUNT(*) FROM bond_coupon_payments").fetchone()[0]
            redemption = conn.execute(
                "SELECT COUNT(*), SUM(amount_cents) FROM bond_redemptions").fetchone()
            self.bonds.process_coupon_payments(conn)  # повторный вызов не дублирует выплаты
            coupons_again = conn.execute("SELECT COUNT(*) FROM bond_coupon_payments").fetchone()[0]
        self.assertGreater(coupons, 0)
        self.assertEqual(coupons, coupons_again)
        self.assertEqual(tuple(redemption), (1, 3 * 100_000))

    # --- вклады
    def test_deposit_calculation(self):
        deposit = self.pages[4]
        deposit.principal.setValue(100_000)
        deposit.rate.setValue(10)
        deposit.years.setValue(1)
        deposit.compounds.setCurrentIndex(0)
        deposit.calculate()
        self.assertTrue(deposit.result.text().startswith("110 000.00"))

    def test_deposit_extreme_values_do_not_show_error_dialog(self):
        deposit = self.pages[4]
        deposit.principal.setValue(1_000_000_000)
        deposit.rate.setValue(100)
        deposit.years.setValue(100)
        for index in range(deposit.compounds.count()):
            deposit.compounds.setCurrentIndex(index)
            self.dialogs.clear()
            deposit.calculate()
            self.assertEqual(self.dialogs, [], f"периодичность #{index}")
        self.assertIn("не сохранён", deposit.interest.text())

    # --- моделирование
    def test_simulation_details_have_real_line_break(self):
        simulation = self.pages[5]
        simulation.simulations.setValue(100)
        simulation.run_projection()
        self.assertNotIn("\\n", simulation.details.text())
        self.assertIn("\n", simulation.details.text())

    def test_simulation_extreme_values_do_not_show_error_dialog(self):
        simulation = self.pages[5]
        with database.connect() as conn:  # крупный портфель, к которому применяется доходность
            conn.execute(
                "INSERT INTO assets(name,ticker,quantity,average_price_cents,current_price_cents) "
                "VALUES('Тест','TST',1000000,100000000,100000000)")
        simulation.refresh()
        simulation.rate.setValue(100)
        simulation.volatility.setValue(100)
        simulation.years.setValue(50)
        simulation.simulations.setValue(1000)
        self.dialogs.clear()
        simulation.run_projection()
        self.assertEqual(self.dialogs, [])

    def test_reports_all_periods(self):
        reports = self.pages[6]
        for index in range(reports.period.count()):
            reports.period.setCurrentIndex(index)
            reports.refresh()


if __name__ == "__main__":
    unittest.main()
