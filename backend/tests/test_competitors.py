import unittest

from pydantic import ValidationError

from routers.competitors import CompetitorInput, CompetitorProductInput, ProductComparisonInput


class CompetitorInputTests(unittest.TestCase):
    def test_accepts_minimal_input_with_defaults(self):
        competitor = CompetitorInput.model_validate({"name": "Pizza Palace"})
        self.assertEqual(competitor.currency, "USD")
        self.assertEqual(competitor.status, "active")
        self.assertIsNone(competitor.referencePriceCents)

    def test_rejects_empty_name(self):
        with self.assertRaises(ValidationError):
            CompetitorInput.model_validate({"name": ""})

    def test_rejects_negative_reference_price(self):
        with self.assertRaises(ValidationError):
            CompetitorInput.model_validate({"name": "Pizza Palace", "referencePriceCents": -100})

    def test_rejects_invalid_currency_length(self):
        with self.assertRaises(ValidationError):
            CompetitorInput.model_validate({"name": "Pizza Palace", "currency": "US"})

    def test_rejects_invalid_status(self):
        with self.assertRaises(ValidationError):
            CompetitorInput.model_validate({"name": "Pizza Palace", "status": "deleted"})

    def test_normalizes_whitespace_and_currency(self):
        competitor = CompetitorInput.model_validate({"name": "  Pizza Palace  ", "currency": "usd"})
        self.assertEqual(competitor.name, "Pizza Palace")
        self.assertEqual(competitor.currency, "USD")

    def test_rejects_non_alpha_currency(self):
        with self.assertRaises(ValidationError):
            CompetitorInput.model_validate({"name": "Pizza Palace", "currency": "U1D"})

    def test_product_and_comparison_bounds(self):
        with self.assertRaises(ValidationError):
            CompetitorProductInput.model_validate({"competitorId": 1, "name": "Pizza", "regularPriceCents": -1})
        with self.assertRaises(ValidationError):
            ProductComparisonInput.model_validate({"ownItemId": 1, "competitorProductId": 2, "matchQuality": 101})


if __name__ == "__main__":
    unittest.main()
