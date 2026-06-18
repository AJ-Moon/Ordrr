# Privacy and Consent

Phase 0 stores consent independently for email, SMS, WhatsApp, and push. Each record includes tenant, customer, status, source, policy version, and timestamp. Denied or withdrawn consent creates an active communication suppression; granting consent deactivates only suppressions created by consent withdrawal.

Phase 1 adds authenticated data export and anonymization, raw-event/chat retention jobs, and tenant/channel frequency caps. Anonymization clears direct customer profile fields, withdraws all channel consents, activates suppressions, and unlinks analytics events while retaining non-identifying financial records required for operations.

The frontend uses first-party random visitor and session identifiers. Authentication can link activity to a customer, but identities must never be merged solely because sessions share a device, address, or network. Communication eligibility requires granted consent, no active suppression, and capacity under the configured frequency window.

Defaults are 400 days for raw events and 90 days for chat sessions, controlled by `RAW_EVENT_RETENTION_DAYS` and `CHAT_CONTENT_RETENTION_DAYS`. Raw PII must not be sent to aggregate AI analysis.
