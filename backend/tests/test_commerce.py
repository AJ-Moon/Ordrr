import unittest

from fastapi import HTTPException

from services.commerce import RequestedLine, price_menu_lines


class FakeCursor:
    def __init__(self, rows):
        self.rows = rows
        self.executed = []

    def execute(self, query, params):
        self.executed.append((query, params))

    def fetchall(self):
        return self.rows


class CommercePricingTests(unittest.TestCase):
    def test_uses_database_sale_price_and_cost_snapshot(self):
        cursor = FakeCursor([(7, "Pizza", "pizza", "USD", 1500, 1200, 500, 75, True)])
        lines = price_menu_lines(cursor, 3, [RequestedLine(7, 2)])
        self.assertEqual(lines[0].net_unit_price_cents, 1200)
        self.assertEqual(lines[0].line_revenue_cents, 2400)
        self.assertEqual(lines[0].line_margin_cents, 1250)
        self.assertEqual(cursor.executed[0][1], (3, [7]))

    def test_rejects_missing_tenant_item(self):
        cursor = FakeCursor([])
        with self.assertRaises(HTTPException) as raised:
            price_menu_lines(cursor, 3, [RequestedLine(99, 1)])
        self.assertEqual(raised.exception.status_code, 422)

    def test_rejects_unavailable_item(self):
        cursor = FakeCursor([(7, "Pizza", "pizza", "USD", 1500, None, 500, 0, False)])
        with self.assertRaises(HTTPException) as raised:
            price_menu_lines(cursor, 3, [RequestedLine(7, 1)])
        self.assertEqual(raised.exception.status_code, 409)


if __name__ == "__main__":
    unittest.main()
