import unittest

from pydantic import ValidationError

from routers.opportunities import CommentRequest, DismissRequest


class OpportunityRouterTests(unittest.TestCase):
    def test_dismissal_reason_is_required(self):
        with self.assertRaises(ValidationError):
            DismissRequest.model_validate({"reason": "x"})

    def test_comment_length_is_bounded(self):
        with self.assertRaises(ValidationError):
            CommentRequest.model_validate({"body": "x" * 2001})


if __name__ == "__main__":
    unittest.main()
