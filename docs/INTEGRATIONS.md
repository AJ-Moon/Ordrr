# Integrations

- PostgreSQL/Supabase: authoritative application database. FastAPI uses `DATABASE_URL`; the browser Supabase client is currently used for realtime order subscriptions.
- OpenAI: current chatbot and menu parser call OpenAI directly. Opportunity explanations use a provider abstraction with structured outputs and audit trail.
- Mapbox: browser address search and delivery-location UX.
- Messaging: mock remains the default. Phase 8 adds opt-in SendGrid email and Twilio SMS/WhatsApp providers; missing credentials fail closed.
- Advertising: Phase 8 adds tenant-scoped integration account scaffolding and health checks. Provider-specific campaign import/export remains future work.
