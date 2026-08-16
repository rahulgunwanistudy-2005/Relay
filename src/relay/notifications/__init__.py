"""relay.notifications — delivery channels and persisted delivery evidence.

Phase 8 populates channels/ (in-app, SMTP), delivery/, templates/. A
NotificationDelivery row is written for every provider attempt; "sent" is never
claimed without a successful provider call.
"""
