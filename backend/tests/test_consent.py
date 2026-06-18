import unittest

from fastapi import HTTPException

from routers.revenue_operator import ConsentUpdateRequest
from services.consent import validate_consent


class ConsentTests(unittest.TestCase):
    def test_normalizes_valid_consent(self):
        self.assertEqual(validate_consent(" Email ", "GRANTED"), ("email", "granted"))

    def test_rejects_unknown_channel(self):
        with self.assertRaises(HTTPException):
            validate_consent("fax", "granted")

    def test_request_rejects_empty_updates(self):
        with self.assertRaises(ValueError):
            ConsentUpdateRequest(consents=[])


if __name__ == "__main__":
    unittest.main()
