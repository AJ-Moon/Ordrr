import unittest
from datetime import datetime, timedelta, timezone

from pydantic import ValidationError

from routers.events import EventInput


class EventValidationTests(unittest.TestCase):
    def base_event(self):
        return {
            "eventId": "event-123456",
            "eventName": "page_viewed",
            "visitorId": "visitor-123456",
            "sessionId": "session-123456",
            "occurredAt": datetime.now(timezone.utc).isoformat(),
        }

    def test_accepts_canonical_client_event(self):
        event = EventInput.model_validate(self.base_event())
        self.assertEqual(event.eventName, "page_viewed")

    def test_rejects_server_event_from_browser(self):
        raw = self.base_event()
        raw["eventName"] = "order_completed"
        with self.assertRaises(ValidationError):
            EventInput.model_validate(raw)

    def test_rejects_expired_raw_event(self):
        raw = self.base_event()
        raw["occurredAt"] = (datetime.now(timezone.utc) - timedelta(days=31)).isoformat()
        with self.assertRaises(ValidationError):
            EventInput.model_validate(raw)


if __name__ == "__main__":
    unittest.main()
