"""Authentication routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from relay.api.deps import get_current_user, get_db
from relay.api.schemas.auth import (
    LoginRequest,
    RegisterRequest,
    TokenResponse,
    UserResponse,
)
from relay.core.application import accounts
from relay.core.application.errors import NotAuthorized
from relay.core.models import User

router = APIRouter(prefix="/v1", tags=["auth"])


@router.post("/auth/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
def register(body: RegisterRequest, db: Session = Depends(get_db)) -> TokenResponse:
    user, token = accounts.register(
        db, email=body.email, password=body.password, display_name=body.display_name
    )
    return TokenResponse(access_token=token, user_id=user.id)


@router.post("/auth/login", response_model=TokenResponse)
def login(body: LoginRequest, db: Session = Depends(get_db)) -> TokenResponse:
    try:
        user, token = accounts.login(db, email=body.email, password=body.password)
    except NotAuthorized as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid credentials"
        ) from exc
    return TokenResponse(access_token=token, user_id=user.id)


@router.post("/auth/logout")
def logout(
    authorization: str = Header(),
    _user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, bool]:
    token = authorization[7:].strip()
    accounts.logout(db, token=token)
    return {"ok": True}


@router.get("/me", response_model=UserResponse)
def me(user: User = Depends(get_current_user)) -> User:
    return user
