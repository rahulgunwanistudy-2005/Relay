"""Request dependencies: DB session, current user, membership authorization."""

from __future__ import annotations

import uuid
from collections.abc import Iterator

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from relay.core.application import accounts, households
from relay.core.application.errors import NotAuthorized, NotFound
from relay.core.models import Membership, User
from relay.db.session import SessionLocal


def get_db() -> Iterator[Session]:
    """One session/transaction per request: commit on success, rollback on error."""
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def get_current_user(
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> User:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="missing bearer token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    token = authorization[7:].strip()
    try:
        return accounts.authenticate(db, token=token)
    except NotAuthorized as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc


def require_membership(
    household_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Membership:
    """Authorize a household-scoped request. Fails closed (404) for non-members
    so resource existence is not leaked across tenants."""
    try:
        return households.require_membership(db, user_id=user.id, household_id=household_id)
    except NotFound as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="household not found"
        ) from exc
