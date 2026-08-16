"""Account services: registration, login, session lifecycle."""

from __future__ import annotations

import datetime as dt

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from relay.core.application.errors import Conflict, NotAuthorized
from relay.core.clock import Clock, SystemClock
from relay.core.enums import AccountState
from relay.core.models import User, UserSession
from relay.core.security import (
    generate_token,
    hash_password,
    hash_token,
    normalize_email,
    verify_password,
)

DEFAULT_SESSION_TTL = dt.timedelta(days=30)


def register(
    session: Session,
    *,
    email: str,
    password: str,
    display_name: str,
    clock: Clock = SystemClock(),
    ttl: dt.timedelta = DEFAULT_SESSION_TTL,
) -> tuple[User, str]:
    user = User(
        email=normalize_email(email),
        password_hash=hash_password(password),
        display_name=display_name.strip(),
    )
    session.add(user)
    try:
        session.flush()
    except IntegrityError as exc:
        session.rollback()
        raise Conflict("email is already registered") from exc

    token = _create_session(session, user, clock=clock, ttl=ttl)
    return user, token


def login(
    session: Session,
    *,
    email: str,
    password: str,
    clock: Clock = SystemClock(),
    ttl: dt.timedelta = DEFAULT_SESSION_TTL,
) -> tuple[User, str]:
    user = session.execute(
        select(User).where(User.email == normalize_email(email))
    ).scalar_one_or_none()
    # Verify a hash even when the user is missing, to blunt timing/enumeration.
    reference = user.password_hash if user else _DUMMY_HASH
    ok = verify_password(password, reference)
    if not user or not ok or user.account_state is not AccountState.active:
        raise NotAuthorized("invalid credentials")
    token = _create_session(session, user, clock=clock, ttl=ttl)
    return user, token


def authenticate(session: Session, *, token: str, clock: Clock = SystemClock()) -> User:
    now = clock.now()
    row = session.execute(
        select(UserSession, User)
        .join(User, User.id == UserSession.user_id)
        .where(UserSession.token_hash == hash_token(token))
    ).one_or_none()
    if row is None:
        raise NotAuthorized("invalid session")
    user_session, user = row
    if user_session.revoked_at is not None:
        raise NotAuthorized("session revoked")
    if user_session.expires_at <= now:
        raise NotAuthorized("session expired")
    if user.account_state is not AccountState.active:
        raise NotAuthorized("account disabled")
    return user


def logout(session: Session, *, token: str, clock: Clock = SystemClock()) -> None:
    user_session = session.execute(
        select(UserSession).where(UserSession.token_hash == hash_token(token))
    ).scalar_one_or_none()
    if user_session is not None and user_session.revoked_at is None:
        user_session.revoked_at = clock.now()


def _create_session(session: Session, user: User, *, clock: Clock, ttl: dt.timedelta) -> str:
    token = generate_token()
    session.add(
        UserSession(
            user_id=user.id,
            token_hash=hash_token(token),
            expires_at=clock.now() + ttl,
        )
    )
    session.flush()
    return token


# A precomputed hash so login of a nonexistent user still does argon2 work.
_DUMMY_HASH = hash_password("relay-dummy-password-not-used")
