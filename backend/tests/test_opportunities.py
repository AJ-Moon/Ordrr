import os
import unittest
from unittest.mock import patch

from services.ai.provider import DisabledAIProvider
from services.opportunities import (
    checkout_candidates,
    clamp_score,
    item_candidates,
    priority_score,
    search_candidates,
)


class OpportunityScoringTests(unittest.TestCase):
    def test_scores_are_bounded(self):
        self.assertEqual(clamp_score(-1), 0)
        self.assertEqual(clamp_score(101), 100)
        self.assertGreaterEqual(priority_score(100, 100, 0, 100), 0)
        self.assertLessEqual(priority_score(100, 100, 0, 100), 100)

    def test_item_detector_uses_persisted_classification(self):
        rows = [(7, "Test Pizza", "LEAKING", 80, {"revenueCents": 10000})]
        candidates = item_candidates(rows, 0.5)
        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0].type, "HIGH_ATTENTION_LOW_CONVERSION")
        self.assertEqual(candidates[0].confidence_score, 40)
        self.assertEqual(candidates[0].estimated_revenue_impact_cents, 1000)

    def test_search_detector_hides_small_samples(self):
        self.assertEqual(search_candidates([("pizza", 9, 9, 0, 0, 0)], 1), [])
        found = search_candidates([("pizza", 20, 10, 2, 1, 0)], 1)
        self.assertEqual(found[0].type, "SEARCH_NO_RESULT")

    def test_checkout_detector_can_emit_failure_and_drop(self):
        found = checkout_candidates([("PAYMENT", 100, 50, 20, 0, 0)], 1)
        self.assertEqual({candidate.type for candidate in found}, {"PAYMENT_FAILURE", "CHECKOUT_DROP"})

    def test_disabled_ai_is_a_valid_fallback(self):
        result = DisabledAIProvider().generate_opportunity_card({"metric": 1})
        self.assertEqual(result.validation_result, "skipped")
        self.assertIsNone(result.card)

    def test_provider_selection_without_key_never_calls_network(self):
        from services.ai.provider import get_ai_provider
        with patch.dict(os.environ, {}, clear=True):
            self.assertIsInstance(get_ai_provider(), DisabledAIProvider)


if __name__ == "__main__":
    unittest.main()
