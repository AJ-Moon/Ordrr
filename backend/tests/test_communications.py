import unittest

from services.communications import check_communication_eligibility


class Cursor:
    def __init__(self, results):
        self.results = iter(results)
        self.current = None

    def execute(self, _query, _params):
        self.current = next(self.results)

    def fetchone(self):
        return self.current


class CommunicationTests(unittest.TestCase):
    def test_suppression_blocks_before_consent_lookup(self):
        result = check_communication_eligibility(
            Cursor([(1,)]), tenant_id=1, customer_id="c1", channel="email"
        )
        self.assertFalse(result.allowed)
        self.assertEqual(result.reason, "suppressed")

    def test_frequency_limit_blocks(self):
        result = check_communication_eligibility(
            Cursor([None, ("granted",), (2, 168), (2,)]),
            tenant_id=1,
            customer_id="c1",
            channel="sms",
        )
        self.assertFalse(result.allowed)
        self.assertEqual(result.reason, "frequency_limit_reached")


if __name__ == "__main__":
    unittest.main()
