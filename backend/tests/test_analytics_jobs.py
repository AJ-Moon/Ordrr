import unittest
from datetime import date, datetime, timezone
from unittest.mock import patch

from services import analytics_jobs
from services.analytics_jobs import (
    _target_date,
    aggregate_daily_full,
    refresh_basket_associations,
    refresh_chat_metrics,
    refresh_customer_metrics,
)


class FakeCursor:
    def __init__(self):
        self.executed = []

    def execute(self, query, params=None):
        self.executed.append((query, params))


class TargetDateTests(unittest.TestCase):
    def test_uses_metadata_date_when_present(self):
        self.assertEqual(_target_date({"date": "2026-01-05"}), date(2026, 1, 5))

    def test_defaults_to_today_when_absent(self):
        # _target_date uses the UTC clock; compare against the same clock so the
        # test is not flaky around the local-vs-UTC midnight boundary.
        self.assertEqual(_target_date({}), datetime.now(timezone.utc).date())


class RefreshCustomerMetricsTests(unittest.TestCase):
    def test_deletes_then_inserts_for_metric_date(self):
        cursor = FakeCursor()
        refresh_customer_metrics(cursor, 3, {"date": "2026-01-05"})
        self.assertEqual(len(cursor.executed), 2)
        delete_query, delete_params = cursor.executed[0]
        self.assertIn("DELETE FROM daily_customer_metrics", delete_query)
        self.assertEqual(delete_params, (3, date(2026, 1, 5)))
        insert_query, insert_params = cursor.executed[1]
        self.assertIn("INSERT INTO daily_customer_metrics", insert_query)
        self.assertEqual(insert_params, (3, date(2026, 1, 5), 3, 3, date(2026, 1, 5)))


class RefreshBasketAssociationsTests(unittest.TestCase):
    def test_window_defaults_to_ninety_days(self):
        cursor = FakeCursor()
        refresh_basket_associations(cursor, 3, {"date": "2026-01-05"})
        window_end = date(2026, 1, 5)
        window_start = date(2025, 10, 7)
        delete_query, delete_params = cursor.executed[0]
        self.assertIn("DELETE FROM basket_associations", delete_query)
        self.assertEqual(delete_params, (3, window_start, window_end))
        insert_query, insert_params = cursor.executed[1]
        self.assertIn("INSERT INTO basket_associations", insert_query)
        self.assertEqual(insert_params, (3, window_start, window_end, 3, window_start, window_end))

    def test_window_respects_env_override(self):
        cursor = FakeCursor()
        with patch.dict("os.environ", {"BASKET_ASSOCIATION_WINDOW_DAYS": "14"}):
            refresh_basket_associations(cursor, 3, {"date": "2026-01-05"})
        _, delete_params = cursor.executed[0]
        self.assertEqual(delete_params, (3, date(2025, 12, 22), date(2026, 1, 5)))

    def test_window_below_minimum_is_clamped_to_seven_days(self):
        cursor = FakeCursor()
        with patch.dict("os.environ", {"BASKET_ASSOCIATION_WINDOW_DAYS": "1"}):
            refresh_basket_associations(cursor, 3, {"date": "2026-01-05"})
        _, delete_params = cursor.executed[0]
        self.assertEqual(delete_params, (3, date(2025, 12, 29), date(2026, 1, 5)))


class RefreshChatMetricsTests(unittest.TestCase):
    def test_deletes_then_inserts_for_metric_date(self):
        cursor = FakeCursor()
        refresh_chat_metrics(cursor, 3, {"date": "2026-01-05"})
        self.assertEqual(len(cursor.executed), 2)
        delete_query, delete_params = cursor.executed[0]
        self.assertIn("DELETE FROM daily_chat_metrics", delete_query)
        self.assertEqual(delete_params, (3, date(2026, 1, 5)))
        insert_query, insert_params = cursor.executed[1]
        self.assertIn("INSERT INTO daily_chat_metrics", insert_query)
        self.assertIn("chat_message_sent", insert_query)
        self.assertEqual(insert_params, (3, date(2026, 1, 5), 3, date(2026, 1, 5)))


class AggregateDailyFullTests(unittest.TestCase):
    def test_calls_all_aggregation_steps_in_order(self):
        calls = []
        cursor = FakeCursor()
        metadata = {"date": "2026-01-05"}
        with patch.object(analytics_jobs, "aggregate_daily", side_effect=lambda *a: calls.append("item")) as m1, \
             patch.object(analytics_jobs, "refresh_customer_metrics", side_effect=lambda *a: calls.append("customer")) as m2, \
             patch.object(analytics_jobs, "refresh_basket_associations", side_effect=lambda *a: calls.append("basket")) as m3, \
             patch.object(analytics_jobs, "refresh_chat_metrics", side_effect=lambda *a: calls.append("chat")) as m4, \
             patch.object(analytics_jobs, "refresh_menu_classifications", side_effect=lambda *a: calls.append("matrix")) as m5:
            aggregate_daily_full(cursor, 3, metadata)
        self.assertEqual(calls, ["item", "customer", "basket", "chat", "matrix"])
        for mock in (m1, m2, m3, m4, m5):
            mock.assert_called_once_with(cursor, 3, metadata)


if __name__ == "__main__":
    unittest.main()
