import unittest
from unittest.mock import patch

import routers.chatbot as cb
from services.entitlements import FeatureAccess


class ChatbotEntitlementGateTests(unittest.TestCase):
    """The public AI chatbot must be gated by the ai.chatbot plan entitlement and
    must fail gracefully (no error, no OpenAI call) when the plan lacks it."""

    def _call(self, access):
        body = cb.ChatRequest(message="hi", session_id=None, conversation_history=[])
        with patch.object(cb, "_enforce_chat_rate_limits", lambda *a, **k: None), \
             patch.object(cb, "get_feature_access", return_value=access), \
             patch.object(cb, "get_db") as gdb:
            result = cb.chat(body=body, restaurant_id=1, current_user=None)
            return result, gdb

    def test_disabled_plan_returns_graceful_response_without_db_or_openai(self):
        access = FeatureAccess(key="ai.chatbot", enabled=False, limit=None, source="plan")
        result, gdb = self._call(access)
        self.assertTrue(result["disabled"])
        self.assertIsNone(result["session_id"])
        self.assertIsNone(result["action"])
        # Gate returns before any DB/model work.
        gdb.assert_not_called()

    def test_over_usage_limit_returns_graceful_capacity_message(self):
        from fastapi import HTTPException
        access = FeatureAccess(key="ai.chatbot", enabled=True, limit=100, source="plan")
        body = cb.ChatRequest(message="hi", session_id=None, conversation_history=[])
        with patch.object(cb, "_enforce_chat_rate_limits", lambda *a, **k: None), \
             patch.object(cb, "get_feature_access", return_value=access), \
             patch.object(cb, "consume_feature_usage", side_effect=HTTPException(status_code=429, detail="x")), \
             patch.object(cb, "get_db") as gdb:
            result = cb.chat(body=body, restaurant_id=1, current_user=None)
        self.assertTrue(result["disabled"])
        gdb.assert_not_called()


if __name__ == "__main__":
    unittest.main()
