import json
import os
import uuid
from urllib import request as urlrequest
from urllib.error import URLError
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Optional

from services.events import emit_server_event


@dataclass(frozen=True)
class MessageResult:
    accepted: bool
    provider: str
    provider_message_id: Optional[str]
    status: str
    error: Optional[str] = None


class MessagingProvider(ABC):
    @abstractmethod
    def send(self, *, channel: str, destination: str, content: dict[str, Any]) -> MessageResult:
        raise NotImplementedError


class EmailProvider(MessagingProvider):
    pass


class SMSProvider(MessagingProvider):
    pass


class WhatsAppProvider(MessagingProvider):
    pass


class MockMessagingProvider(EmailProvider, SMSProvider, WhatsAppProvider):
    def send(self, *, channel: str, destination: str, content: dict[str, Any]) -> MessageResult:
        if not destination:
            return MessageResult(False, "mock", None, "FAILED", "missing_destination")
        return MessageResult(True, "mock", f"mock-{uuid.uuid4()}", "SENT")


class SendGridEmailProvider(EmailProvider):
    def send(self, *, channel: str, destination: str, content: dict[str, Any]) -> MessageResult:
        if channel != "email":
            return MessageResult(False, "sendgrid", None, "FAILED", "unsupported_channel")
        api_key = os.getenv("SENDGRID_API_KEY")
        sender = os.getenv("SENDGRID_FROM_EMAIL")
        if not api_key or not sender:
            return MessageResult(False, "sendgrid", None, "FAILED", "missing_sendgrid_configuration")
        payload = json.dumps({
            "personalizations": [{"to": [{"email": destination}]}],
            "from": {"email": sender},
            "subject": str(content.get("subject") or "A message from your restaurant"),
            "content": [{"type": "text/plain", "value": str(content.get("body") or content.get("template") or "")[:5000]}],
        }).encode()
        req = urlrequest.Request(
            "https://api.sendgrid.com/v3/mail/send",
            data=payload,
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urlrequest.urlopen(req, timeout=10) as response:
                accepted = 200 <= response.status < 300
                return MessageResult(accepted, "sendgrid", response.headers.get("X-Message-Id"), "SENT" if accepted else "FAILED", None if accepted else f"HTTP {response.status}")
        except URLError as exc:
            return MessageResult(False, "sendgrid", None, "FAILED", str(exc)[:200])


class TwilioMessagingProvider(SMSProvider, WhatsAppProvider):
    def send(self, *, channel: str, destination: str, content: dict[str, Any]) -> MessageResult:
        if channel not in {"sms", "whatsapp"}:
            return MessageResult(False, "twilio", None, "FAILED", "unsupported_channel")
        sid = os.getenv("TWILIO_ACCOUNT_SID")
        token = os.getenv("TWILIO_AUTH_TOKEN")
        from_number = os.getenv("TWILIO_WHATSAPP_FROM" if channel == "whatsapp" else "TWILIO_SMS_FROM")
        if not sid or not token or not from_number:
            return MessageResult(False, "twilio", None, "FAILED", "missing_twilio_configuration")
        body = str(content.get("body") or content.get("template") or "")[:1600]
        to_value = f"whatsapp:{destination}" if channel == "whatsapp" and not destination.startswith("whatsapp:") else destination
        from_value = f"whatsapp:{from_number}" if channel == "whatsapp" and not from_number.startswith("whatsapp:") else from_number
        data = f"To={to_value}&From={from_value}&Body={body}".encode()
        req = urlrequest.Request(
            f"https://api.twilio.com/2010-04-01/Accounts/{sid}/Messages.json",
            data=data,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            method="POST",
        )
        import base64
        req.add_header("Authorization", "Basic " + base64.b64encode(f"{sid}:{token}".encode()).decode())
        try:
            with urlrequest.urlopen(req, timeout=10) as response:
                response_body = json.loads(response.read().decode() or "{}")
                accepted = 200 <= response.status < 300
                return MessageResult(accepted, "twilio", response_body.get("sid"), "SENT" if accepted else "FAILED", None if accepted else f"HTTP {response.status}")
        except Exception as exc:
            return MessageResult(False, "twilio", None, "FAILED", str(exc)[:200])


class CompositeMessagingProvider(MessagingProvider):
    def __init__(self) -> None:
        self.email = SendGridEmailProvider()
        self.twilio = TwilioMessagingProvider()

    def send(self, *, channel: str, destination: str, content: dict[str, Any]) -> MessageResult:
        if channel == "email":
            return self.email.send(channel=channel, destination=destination, content=content)
        if channel in {"sms", "whatsapp"}:
            return self.twilio.send(channel=channel, destination=destination, content=content)
        return MessageResult(False, "composite", None, "FAILED", "unsupported_channel")


def get_messaging_provider() -> MessagingProvider:
    provider = os.getenv("MESSAGING_PROVIDER", "mock").strip().lower()
    if provider == "sendgrid_twilio":
        return CompositeMessagingProvider()
    if provider in {"sendgrid", "twilio"}:
        return CompositeMessagingProvider()
    if provider != "mock":
        raise RuntimeError("Unsupported messaging provider configuration")
    return MockMessagingProvider()


def persist_mock_message(
    cursor,
    *,
    tenant_id: int,
    mission_id: int,
    action_id: int,
    customer_id: str,
    subject_type: str,
    subject_id: str,
    channel: str,
    destination: str,
    content: dict[str, Any],
) -> bool:
    cursor.execute(
        """INSERT INTO campaign_messages
           (tenant_id,mission_id,action_id,customer_id,subject_type,subject_id,
            channel,provider,content,status)
           VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb,'QUEUED')
           ON CONFLICT (mission_id,action_id,subject_type,subject_id) DO NOTHING
           RETURNING id""",
        (tenant_id, mission_id, action_id, customer_id, subject_type, subject_id, channel, os.getenv("MESSAGING_PROVIDER", "mock").strip().lower(), json.dumps(content)),
    )
    row = cursor.fetchone()
    if not row:
        return False
    message_id = int(row[0])
    result = get_messaging_provider().send(channel=channel, destination=destination, content=content)
    cursor.execute(
        """UPDATE campaign_messages SET status = %s, provider_message_id = %s,
           failure_reason = %s, updated_at = NOW() WHERE tenant_id = %s AND id = %s""",
        (result.status, result.provider_message_id, result.error, tenant_id, message_id),
    )
    cursor.execute(
        """INSERT INTO message_deliveries
           (tenant_id,campaign_message_id,status,provider_event_id,metadata)
           VALUES (%s,%s,%s,%s,%s::jsonb)""",
        (tenant_id, message_id, result.status, result.provider_message_id, json.dumps({"mock": True})),
    )
    event_name = "message_sent" if result.accepted else "message_failed"
    emit_server_event(
        cursor, tenant_id=tenant_id, event_name=event_name,
        event_id=f"campaign-message:{message_id}:{result.status}", customer_id=customer_id,
        mission_id=str(mission_id), properties={"channel": channel, "campaignMessageId": message_id},
        consent_state="essential",
    )
    return result.accepted
