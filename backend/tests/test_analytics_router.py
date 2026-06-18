import unittest
from datetime import date, timedelta

from fastapi import HTTPException

from routers.analytics import MAX_RANGE_DAYS, _date_range


class DateRangeTests(unittest.TestCase):
    def test_defaults_to_last_thirty_days(self):
        start, end = _date_range(None, None)
        self.assertEqual(end, date.today())
        self.assertEqual((end - start).days, 29)

    def test_uses_provided_range(self):
        start, end = _date_range(date(2026, 1, 1), date(2026, 1, 10))
        self.assertEqual(start, date(2026, 1, 1))
        self.assertEqual(end, date(2026, 1, 10))

    def test_rejects_start_after_end(self):
        with self.assertRaises(HTTPException) as raised:
            _date_range(date(2026, 1, 10), date(2026, 1, 1))
        self.assertEqual(raised.exception.status_code, 422)

    def test_rejects_range_exceeding_max(self):
        start = date(2026, 1, 1)
        end = start + timedelta(days=MAX_RANGE_DAYS + 1)
        with self.assertRaises(HTTPException) as raised:
            _date_range(start, end)
        self.assertEqual(raised.exception.status_code, 422)


if __name__ == "__main__":
    unittest.main()
