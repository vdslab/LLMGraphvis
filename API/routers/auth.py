"""
API endpoints for user authentication.

This module provides routes for user registration, login, and retrieving
the current user's information.
"""
from datetime import timedelta
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

import models, schemas, auth
from database import get_db

router = APIRouter(
    prefix="/auth",
    tags=["authentication"],
    responses={401: {"description": "Unauthorized"}},
)

@router.post("/register", response_model=schemas.User)
def register_user(user: schemas.UserCreate, db: Session = Depends(get_db)):
    """
    Registers a new user.

    Args:
        user: The user's registration information.
        db: The database session.

    Returns:
        The newly created user.
    """
    # Check if username already exists
    db_user = auth.get_user(db, username=user.username)
    if db_user:
        raise HTTPException(
            status_code=400,
            detail="Username already registered"
        )
    
    # Create new user
    hashed_password = auth.get_password_hash(user.password)
    db_user = models.User(
        username=user.username,
        hashed_password=hashed_password
    )
    
    # Save user to database
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    
    return db_user

from fastapi.responses import JSONResponse

@router.post("/token", response_model=schemas.Token)
async def login_for_access_token(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db)
):
    """
    Logs in a user and returns an access token.
    
    Sets the token as an HttpOnly cookie for enhanced security,
    while also returning it in the response body for backward compatibility.

    Args:
        form_data: The user's login credentials.
        db: The database session.

    Returns:
        A JSONResponse with the access token and token type,
        and sets an HttpOnly cookie with the token.
    """
    # Authenticate user
    user = auth.authenticate_user(db, form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Create access token
    access_token_expires = timedelta(minutes=auth.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = auth.create_access_token(
        data={"sub": user.username},
        expires_delta=access_token_expires
    )
    
    # Create response with token in body (for backward compatibility)
    response = JSONResponse(
        content={"access_token": access_token, "token_type": "bearer"}
    )
    
    # Set HttpOnly cookie with the token
    cookie_expires = int(access_token_expires.total_seconds())
    response.set_cookie(
        key="access_token",
        value=f"Bearer {access_token}",
        httponly=True,
        secure=True,  # Requires HTTPS
        samesite="lax",  # Protects against CSRF
        max_age=cookie_expires,
        path="/"  # Available across the entire domain
    )
    
    return response

@router.get("/users/me", response_model=schemas.User)
async def read_users_me(current_user: models.User = Depends(auth.get_current_active_user)):
    """
    Returns the current authenticated user's information.

    Args:
        current_user: The current authenticated user.

    Returns:
        The current user's information.
    """
    return current_user
