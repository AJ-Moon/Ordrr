import unittest
from decimal import Decimal

from core.money import MarginBreakdown, from_cents, percentage_of_cents, to_cents


class MoneyTests(unittest.TestCase):
    def test_decimal_conversion_rounds_half_up(self):
        self.assertEqual(to_cents("10.005"), 1001)
        self.assertEqual(from_cents(1001), Decimal("10.01"))

    def test_percentage_uses_integer_result(self):
        self.assertEqual(percentage_of_cents(999, 20), 200)

    def test_contribution_margin(self):
        margin = MarginBreakdown(5000, 1800, 200, 100, 250, 0)
        self.assertEqual(margin.contribution_margin_cents, 2650)


if __name__ == "__main__":
    unittest.main()
