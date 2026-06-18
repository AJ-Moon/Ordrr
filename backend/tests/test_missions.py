import unittest

from pydantic import ValidationError

from routers.missions import MissionCreate
from services.missions import treatment_group


class MissionEngineTests(unittest.TestCase):
    def test_holdout_assignment_is_sticky(self):
        first = treatment_group(4, "customer", "customer-1", 20)
        self.assertEqual(first, treatment_group(4, "customer", "customer-1", 20))
        self.assertIn(first, {"treatment", "holdout"})

    def test_zero_holdout_always_treatment(self):
        self.assertEqual(treatment_group(4, "cart", "cart-1", 0), "treatment")

    def test_bundle_requires_item_ids(self):
        with self.assertRaises(ValidationError):
            MissionCreate.model_validate({
                "type": "INTELLIGENT_BUNDLE", "name": "Bundle test",
                "objective": "Increase profitable basket attachment.",
                "hypothesis": "A contextual bundle will improve margin per session.",
                "actions": [{"type": "SHOW_CART_UPSELL"}],
            })

    def test_abandoned_cart_action_is_valid(self):
        body = MissionCreate.model_validate({
            "type": "ABANDONED_CART_RECOVERY", "name": "Cart reminder",
            "objective": "Recover eligible abandoned carts without blanket discounts.",
            "hypothesis": "A consented reminder will recover incremental profitable orders.",
            "actions": [{"type": "SEND_EMAIL"}],
        })
        self.assertEqual(body.holdoutPercentage, 10)


if __name__ == "__main__":
    unittest.main()
