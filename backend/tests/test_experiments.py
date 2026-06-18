import unittest

from services.experiments import choose_variant, stable_bucket, two_proportion_interval


class ExperimentEngineTests(unittest.TestCase):
    def test_assignment_is_sticky(self):
        variants = [(10, 50), (20, 50)]
        first = choose_variant(7, "visitor-12345678", variants)
        self.assertEqual(first, choose_variant(7, "visitor-12345678", variants))
        self.assertIn(first, {10, 20})

    def test_weighted_assignment_rejects_empty_weights(self):
        with self.assertRaises(ValueError):
            choose_variant(1, "visitor-12345678", [(1, 0), (2, 0)])

    def test_stable_bucket_is_bounded(self):
        value = stable_bucket("experiment", 1, "visitor", modulo=37)
        self.assertGreaterEqual(value, 0)
        self.assertLess(value, 37)

    def test_confidence_interval_requires_separation(self):
        difference, low, high = two_proportion_interval(10, 100, 30, 100, 0.95)
        self.assertGreater(difference, 0)
        self.assertGreater(low, 0)
        self.assertGreater(high, low)

    def test_raw_difference_can_remain_inconclusive(self):
        _, low, high = two_proportion_interval(1, 10, 2, 10, 0.95)
        self.assertLessEqual(low, 0)
        self.assertGreaterEqual(high, 0)


if __name__ == "__main__":
    unittest.main()
