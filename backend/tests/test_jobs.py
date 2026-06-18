import unittest

from services.jobs import retry_delay


class JobTests(unittest.TestCase):
    def test_retry_delay_is_bounded_exponential(self):
        self.assertEqual(retry_delay(1).total_seconds(), 30)
        self.assertEqual(retry_delay(2).total_seconds(), 60)
        self.assertEqual(retry_delay(20).total_seconds(), 3600)


if __name__ == "__main__":
    unittest.main()
