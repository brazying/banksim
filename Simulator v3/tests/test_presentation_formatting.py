import unittest

from pages import capital_chart_data, format_operation_date


class PresentationFormattingTests(unittest.TestCase):
    def test_operation_datetime_is_localized_for_display(self):
        self.assertEqual(
            format_operation_date("2026-11-18T17:57:05"),
            "18.11.2026 · 17:57",
        )

    def test_date_only_operation_is_localized_for_display(self):
        self.assertEqual(
            format_operation_date("2026-11-18"),
            "18.11.2026",
        )

    def test_hour_granularity_keeps_last_48_snapshots(self):
        snapshots = [
            {
                "captured_at": f"2026-11-{day:02d}T{hour:02d}:00:00",
                "net_worth_cents": (day * 100 + hour) * 100,
            }
            for day in (17, 18)
            for hour in range(24)
        ]
        labels, values = capital_chart_data(snapshots, "hour")
        self.assertEqual(len(labels), 48)
        self.assertEqual(len(values), 48)
        self.assertEqual(labels[0], "17.11 00:00")

    def test_daily_granularity_uses_last_snapshot_per_day(self):
        snapshots = [
            {"captured_at": "2026-11-17T09:00:00", "net_worth_cents": 100_000},
            {"captured_at": "2026-11-17T18:00:00", "net_worth_cents": 125_000},
            {"captured_at": "2026-11-18T09:00:00", "net_worth_cents": 130_000},
        ]
        labels, values = capital_chart_data(snapshots, "day")
        self.assertEqual(labels, ["17.11", "18.11"])
        self.assertEqual(values, [1250.0, 1300.0])

    def test_weekly_granularity_groups_by_monday(self):
        snapshots = [
            {"captured_at": "2026-11-16T09:00:00", "net_worth_cents": 100_000},
            {"captured_at": "2026-11-18T09:00:00", "net_worth_cents": 125_000},
            {"captured_at": "2026-11-23T09:00:00", "net_worth_cents": 130_000},
        ]
        labels, values = capital_chart_data(snapshots, "week")
        self.assertEqual(labels, ["16.11", "23.11"])
        self.assertEqual(values, [1250.0, 1300.0])

    def test_monthly_granularity_groups_by_month(self):
        snapshots = [
            {"captured_at": "2026-10-01T09:00:00", "net_worth_cents": 100_000},
            {"captured_at": "2026-10-31T23:00:00", "net_worth_cents": 125_000},
            {"captured_at": "2026-11-01T09:00:00", "net_worth_cents": 130_000},
        ]
        labels, values = capital_chart_data(snapshots, "month")
        self.assertEqual(labels, ["10.2026", "11.2026"])
        self.assertEqual(values, [1250.0, 1300.0])

    def test_empty_history_produces_empty_chart_data(self):
        self.assertEqual(capital_chart_data([], "day"), ([], []))


if __name__ == "__main__":
    unittest.main()
