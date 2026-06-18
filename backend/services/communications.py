from dataclasses import dataclass


@dataclass(frozen=True)
class CommunicationEligibility:
    allowed: bool
    reason: str
    sent_in_window: int = 0
    limit: int = 0


def check_communication_eligibility(cursor, *, tenant_id: int, customer_id: str, channel: str) -> CommunicationEligibility:
    cursor.execute(
        """SELECT 1 FROM communication_suppressions
           WHERE tenant_id = %s AND customer_id = %s AND channel = %s AND active = TRUE""",
        (tenant_id, customer_id, channel),
    )
    if cursor.fetchone():
        return CommunicationEligibility(False, "suppressed")

    cursor.execute(
        """SELECT status FROM customer_consents
           WHERE tenant_id = %s AND customer_id = %s AND channel = %s""",
        (tenant_id, customer_id, channel),
    )
    consent = cursor.fetchone()
    if not consent or consent[0] != "granted":
        return CommunicationEligibility(False, "consent_not_granted")

    cursor.execute(
        """SELECT max_messages, window_hours FROM communication_frequency_limits
           WHERE tenant_id = %s AND channel = %s""",
        (tenant_id, channel),
    )
    limit_row = cursor.fetchone()
    if not limit_row:
        return CommunicationEligibility(False, "frequency_limit_not_configured")
    limit, window_hours = int(limit_row[0]), int(limit_row[1])
    cursor.execute(
        """SELECT count(*) FROM analytics_events
           WHERE tenant_id = %s AND customer_id = %s AND event_name = 'message_sent'
             AND properties->>'channel' = %s
             AND occurred_at >= NOW() - (%s * INTERVAL '1 hour')""",
        (tenant_id, customer_id, channel, window_hours),
    )
    sent = int(cursor.fetchone()[0])
    if sent >= limit:
        return CommunicationEligibility(False, "frequency_limit_reached", sent, limit)
    return CommunicationEligibility(True, "eligible", sent, limit)
