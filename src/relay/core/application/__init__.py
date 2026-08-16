"""Application services — transaction boundaries and orchestration.

Services translate authenticated intent into atomic domain mutations. They own
locking, version checks, idempotency, event append, and outbox writes. No
network/LLM/email calls happen inside these transactions.
"""
