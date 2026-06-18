import unittest

from pydantic import ValidationError

from routers.advanced_conversion import OrderArchitectRequest, PrivateOfferCreate
from services.advanced_conversion import compute_private_offer_discount


class Phase78AdvancedConversionTests(unittest.TestCase):
    def test_private_offer_discount_caps_percent_and_fixed(self):
        self.assertEqual(
            compute_private_offer_discount(
                subtotal_cents=5000,
                discount_type="PERCENT",
                discount_value=20,
                max_discount_cents=700,
            ),
            700,
        )
        self.assertEqual(
            compute_private_offer_discount(
                subtotal_cents=1200,
                discount_type="FIXED",
                discount_value=2000,
                max_discount_cents=None,
            ),
            1200,
        )

    def test_private_offer_rejects_over_100_percent(self):
        with self.assertRaises(ValidationError):
            PrivateOfferCreate.model_validate({
                "code": "TOO-MUCH",
                "title": "Too much",
                "description": "This offer should be rejected before persistence.",
                "discountType": "PERCENT",
                "discountValue": 150,
            })

    def test_order_architect_bounds_party_and_budget(self):
        valid = OrderArchitectRequest.model_validate({
            "visitorId": "visitor-123",
            "sessionId": "session-123",
            "budgetCents": 2500,
            "partySize": 3,
            "dietaryConstraints": ["vegetarian"],
        })
        self.assertEqual(valid.partySize, 3)
        with self.assertRaises(ValidationError):
            OrderArchitectRequest.model_validate({
                "visitorId": "visitor-123",
                "sessionId": "session-123",
                "budgetCents": 2500,
                "partySize": 40,
            })


if __name__ == "__main__":
    unittest.main()
