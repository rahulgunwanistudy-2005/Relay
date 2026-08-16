"""relay.worker — durable, idempotent background processing.

Phase 0 provides the process skeleton, an injectable Clock, and a heartbeat so
readiness is observable. Phase 7 adds outbox/reminder claiming via
``FOR UPDATE SKIP LOCKED`` with leases, retries, and dead-lettering.
"""
