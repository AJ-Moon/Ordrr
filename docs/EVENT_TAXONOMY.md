# Event Taxonomy

Status: Phase 1 ingestion and first-party tracking implemented.

Client authority covers views, impressions, searches, cart UI actions, checkout steps, promotion interactions, chat interactions, contact identification, and consent UI changes. Server authority covers cart creation, order lifecycle, availability, messaging delivery, mission lifecycle, experiment exposure, and conversion.

Client events: `page_viewed`, `menu_viewed`, `category_impression`, `category_viewed`, `item_impression`, `item_viewed`, `modifier_group_viewed`, `modifier_selected`, `item_added_to_cart`, `item_removed_from_cart`, `cart_viewed`, `cart_value_changed`, `checkout_started`, `checkout_step_viewed`, `checkout_step_completed`, `delivery_area_checked`, `delivery_fee_shown`, `minimum_order_blocked`, `payment_method_selected`, `payment_started`, `payment_failed`, `search_performed`, `search_result_clicked`, `promotion_impression`, `promotion_clicked`, `chat_opened`, `chat_message_sent`, `chat_recommendation_shown`, `chat_recommendation_clicked`, `order_architect_started`, `order_architect_cart_created`, `contact_identified`, and `consent_updated`.

Server events: `cart_created`, `cart_abandoned_candidate`, `order_created`, `order_completed`, `order_cancelled`, `order_refunded`, `item_marked_unavailable`, `item_marked_available`, messaging lifecycle events, mission lifecycle events, and experiment exposure/conversion events. Only currently implemented commerce transitions emit records; the remaining names reserve the canonical contract for later phases.

Every event requires `eventId`, `eventName`, `visitorId`, `sessionId`, and `occurredAt`. The server supplies tenant and receive time. Schema version and consent state have defaults; entity and attribution fields are optional. Item, location, and order IDs are checked for tenant ownership. `(tenant_id, event_id)` is the deduplication key, and duplicate submissions return a `duplicate` result without another row.

`POST /api/v1/events/batch` accepts 1-100 events and returns partial per-event results. Browser events older than 30 days or more than 10 minutes in the future are rejected. Default limits are 256 KiB per request and 3,000 submitted events per tenant per minute.
