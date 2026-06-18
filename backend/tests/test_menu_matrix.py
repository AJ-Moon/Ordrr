import unittest

from services.menu_matrix import classify_item


class MenuMatrixTests(unittest.TestCase):
    def test_insufficient_data_wins_before_quadrant(self):
        result = classify_item(
            impressions=10, detail_sessions=8, purchase_count=6,
            category_attention=0.2, category_conversion=0.2, minimum_sample=20,
        )
        self.assertEqual(result[0], "INSUFFICIENT_DATA")
        self.assertEqual(result[3], 0)

    def test_classifies_all_quadrants(self):
        cases = [
            ((100, 50, 20, 0.4, 0.3), "HERO"),
            ((100, 50, 5, 0.4, 0.3), "LEAKING"),
            ((100, 20, 10, 0.4, 0.3), "HIDDEN_WINNER"),
            ((100, 20, 2, 0.4, 0.3), "WEAK"),
        ]
        for values, expected in cases:
            with self.subTest(expected=expected):
                result = classify_item(
                    impressions=values[0], detail_sessions=values[1], purchase_count=values[2],
                    category_attention=values[3], category_conversion=values[4], minimum_sample=20,
                )
                self.assertEqual(result[0], expected)
                self.assertGreater(result[3], 0)


if __name__ == "__main__":
    unittest.main()
