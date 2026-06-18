import unittest

from pydantic import ValidationError

from routers.experiments import ExperimentCreate


BASE = {
    "type": "BUTTON_COPY",
    "name": "Homepage call to action",
    "hypothesis": "Clearer copy will improve completed order conversion.",
    "conflictKey": "home:primary-cta",
    "variants": [
        {"key": "control", "name": "Control", "isControl": True},
        {"key": "treatment", "name": "Treatment"},
    ],
}


class ExperimentRouterTests(unittest.TestCase):
    def test_requires_exactly_one_control(self):
        body = {**BASE, "variants": [{"key": "a", "name": "A"}, {"key": "b", "name": "B"}]}
        with self.assertRaises(ValidationError):
            ExperimentCreate.model_validate(body)

    def test_variant_keys_are_unique(self):
        body = {**BASE, "variants": [{"key": "a", "name": "A", "isControl": True}, {"key": "a", "name": "B"}]}
        with self.assertRaises(ValidationError):
            ExperimentCreate.model_validate(body)


if __name__ == "__main__":
    unittest.main()
