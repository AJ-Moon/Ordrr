import unittest

from pydantic import ValidationError

from routers.missions import MissionCreate
from routers.operational_missions import CapacitySettingInput, ProductConceptInput
from services.missions import quiet_hour_candidate_status


class Phase6OperationalMissionTests(unittest.TestCase):
    def test_quiet_hour_candidate_requires_spare_capacity_and_inventory(self):
        status, reason = quiet_hour_candidate_status(
            observed_orders=4,
            normal_capacity_orders=10,
            target_utilization=0.75,
            cancellation_rate=0.05,
            eligible_item_count=3,
        )
        self.assertEqual(status, "CANDIDATE")
        self.assertEqual(reason, "quiet_capacity_available")

    def test_quiet_hour_candidate_blocks_stock_and_cancellations(self):
        stock_status, stock_reason = quiet_hour_candidate_status(
            observed_orders=2,
            normal_capacity_orders=10,
            target_utilization=0.75,
            cancellation_rate=0.01,
            eligible_item_count=0,
        )
        cancel_status, cancel_reason = quiet_hour_candidate_status(
            observed_orders=2,
            normal_capacity_orders=10,
            target_utilization=0.75,
            cancellation_rate=0.40,
            eligible_item_count=2,
        )
        self.assertEqual((stock_status, stock_reason), ("BLOCKED", "no_margin_qualified_inventory"))
        self.assertEqual((cancel_status, cancel_reason), ("BLOCKED", "cancellation_rate_too_high"))

    def test_capacity_settings_validate_order_window_and_capacity(self):
        with self.assertRaises(ValidationError):
            CapacitySettingInput.model_validate({
                "locationId": 1,
                "weekday": 1,
                "timeStart": "18:00",
                "timeEnd": "17:00",
                "normalCapacityOrders": 10,
                "maximumCapacityOrders": 12,
            })
        with self.assertRaises(ValidationError):
            CapacitySettingInput.model_validate({
                "locationId": 1,
                "weekday": 1,
                "timeStart": "14:00",
                "timeEnd": "17:00",
                "normalCapacityOrders": 10,
                "maximumCapacityOrders": 5,
            })

    def test_phase6_mission_type_validation(self):
        quiet = MissionCreate.model_validate({
            "type": "QUIET_HOUR_DEMAND",
            "name": "Quiet afternoon lift",
            "objective": "Increase profitable orders during low utilization windows.",
            "hypothesis": "A capacity-aware banner can create incremental orders without operational strain.",
            "actions": [{"type": "SHOW_PERSONALIZED_BANNER"}],
        })
        product = MissionCreate.model_validate({
            "type": "NEW_PRODUCT_DEMAND_TEST",
            "name": "Test spicy lunch bowl",
            "objective": "Measure qualified interest before adding a new menu item.",
            "hypothesis": "A waitlist page will reveal whether the concept has enough demand.",
            "actions": [{"type": "CREATE_LANDING_PAGE"}],
        })
        self.assertEqual(quiet.type, "QUIET_HOUR_DEMAND")
        self.assertEqual(product.primaryMetric, "incremental_orders")

    def test_preorder_concepts_require_priced_variant(self):
        with self.assertRaises(ValidationError):
            ProductConceptInput.model_validate({
                "name": "Spicy lunch bowl",
                "description": "A limited preorder concept for a new spicy lunch bowl.",
                "category": "Bowls",
                "estimatedCostCents": 350,
                "estimatedPreparationTimeMinutes": 12,
                "presentationMode": "PREORDER",
                "variants": [{"variantKey": "a", "name": "Bowl A", "description": "The primary preorder concept."}],
            })


if __name__ == "__main__":
    unittest.main()
