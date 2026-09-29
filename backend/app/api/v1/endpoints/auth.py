from datetime import timedelta
from typing import Any, Dict, Optional

from fastapi import APIRouter, Cookie, Depends, HTTPException, Response, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app import schemas
from app.core import database
from app.core import security as auth
from common import models

router = APIRouter(prefix="/auth", tags=["auth"])


def _issue_token(response: Response, user: models.User) -> Dict[str, str]:
    """Create an access token for `user`, set it as the auth cookie, and return it.

    The token carries the user's `token_version` as `ver`; bumping the version
    (on password change) invalidates every token issued before.
    """
    access_token = auth.create_access_token(
        data={"sub": user.username, "ver": user.token_version or 0},
        expires_delta=timedelta(minutes=auth.ACCESS_TOKEN_EXPIRE_MINUTES),
    )

    # Set cookie for browser clients
    response.set_cookie(
        key="access_token",
        value=f"Bearer {access_token}",
        httponly=True,
        max_age=auth.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        samesite="lax",
        secure=auth.COOKIE_SECURE,
    )

    return {"access_token": access_token, "token_type": "bearer"}


@router.post("/register", response_model=schemas.Token)
def register(
    user: schemas.UserCreate, response: Response, db: Session = Depends(database.get_db)
):
    """
    Register a new user with username and password.
    """
    db_user = (
        db.query(models.User).filter(models.User.username == user.username).first()
    )
    if db_user:
        raise HTTPException(status_code=409, detail="Username already registered")

    hashed_password = auth.get_password_hash(user.password)
    db_user = models.User(username=user.username, hashed_password=hashed_password)
    db.add(db_user)
    db.commit()
    db.refresh(db_user)

    return _issue_token(response, db_user)


@router.post("/token", response_model=schemas.Token)
def login_for_access_token(
    response: Response,
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(database.get_db),
):
    """
    OAuth2 compatible token login, get an access token for future requests.
    This endpoint is used by the Swagger UI for authentication.
    """
    user = (
        db.query(models.User).filter(models.User.username == form_data.username).first()
    )
    if not user or not auth.verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return _issue_token(response, user)


def _cookie_payload(access_token: Optional[str]) -> Optional[Dict[str, Any]]:
    if not access_token:
        return None
    try:
        scheme, cookie_token = access_token.split()
    except ValueError:
        return None
    if scheme.lower() != "bearer":
        return None
    return auth.decode_access_token(cookie_token)


def _user_for_payload(
    db: Session, payload: Optional[Dict[str, Any]]
) -> Optional[models.User]:
    """The user a token names, or None if it names nobody or is out of date."""
    if not payload or not payload.get("sub"):
        return None
    user = db.query(models.User).filter(models.User.username == payload["sub"]).first()
    # Tokens issued before `ver` existed count as version 0.
    if user is None or payload.get("ver", 0) != (user.token_version or 0):
        return None
    return user


async def get_current_user(
    db: Session = Depends(database.get_db),
    bearer_payload: Optional[Dict[str, Any]] = Depends(auth.get_token_payload),
    access_token: Optional[str] = Cookie(None),
):
    """
    Get the current authenticated user.

    This uses the Bearer token first (for API/Swagger clients) but also supports
    cookie-based auth for browser clients. A token whose `ver` no longer matches
    the user's `token_version` is rejected.
    """
    user = _user_for_payload(db, bearer_payload)
    if user is None:
        user = _user_for_payload(db, _cookie_payload(access_token))

    # If we still don't have a user, authentication failed
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return user


@router.get("/users/me", response_model=schemas.User)
def read_users_me(current_user: models.User = Depends(get_current_user)):
    """
    Get details of the currently authenticated user.
    Used to test authentication in Swagger UI.
    """
    return current_user


@router.post("/change-password", response_model=schemas.Token)
def change_password(
    body: schemas.PasswordChange,
    response: Response,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(database.get_db),
):
    """
    Change the current user's password.

    Signs the user out of every other session (their tokens carry the old
    `token_version`) and returns a fresh token for this one.
    """
    if not auth.verify_password(body.current_password, current_user.hashed_password):
        raise HTTPException(status_code=400, detail="Current password is incorrect")
    if body.new_password == body.current_password:
        raise HTTPException(
            status_code=400, detail="New password must differ from the current one"
        )

    current_user.hashed_password = auth.get_password_hash(body.new_password)
    current_user.token_version = (current_user.token_version or 0) + 1
    db.commit()
    db.refresh(current_user)

    return _issue_token(response, current_user)


@router.post("/logout")
def logout(response: Response):
    """
    Logout a user by removing the authentication cookie.
    Note: For API clients using Bearer tokens, the token remains valid until it
    expires or the password is changed.
    """
    response.delete_cookie("access_token")
    return {"message": "Logged out successfully"}
