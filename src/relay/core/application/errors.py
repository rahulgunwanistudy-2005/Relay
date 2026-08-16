"""Typed application errors. Routers translate these to HTTP; services never
import a web framework."""

from __future__ import annotations


class ApplicationError(Exception):
    """Base for all application-service errors."""


class NotFound(ApplicationError):
    pass


class NotAuthorized(ApplicationError):
    pass


class Conflict(ApplicationError):
    """A precondition failed in a way a retry with fresh state might resolve."""


class StaleContract(Conflict):
    """The contract was agreed against a scope/ownership version that has moved."""


class InvalidState(ApplicationError):
    """The operation is not valid for the current status of the resource."""
