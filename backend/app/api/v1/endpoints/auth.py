from fastapi import APIRouter, Depends, HTTPException, status, Response, Cookie
from sqlalchemy.orm import Session
from fastapi.security import OAuth2PasswordRequestForm
from datetime import timedelta
from typing import Optional
from app import models, schemas
from app.core import security as auth
from app.core import database

router = APIRouter(
    prefix="/auth",
    tags=["auth"]
)

@router.post("/register", response_model=schemas.Token)
def register(user: schemas.UserCreate, response: Response, db: Session = Depends(database.get_db)):
    """
    Register a new user with username and password.
    """
    db_user = db.query(models.User).filter(models.User.username == user.username).first()
    if db_user:
        raise HTTPException(status_code=409, detail="Username already registered")
    
    hashed_password = auth.get_password_hash(user.password)
    db_user = models.User(username=user.username, hashed_password=hashed_password)
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    
    access_token_expires = timedelta(minutes=auth.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = auth.create_access_token(
        data={"sub": db_user.username}, expires_delta=access_token_expires
    )
    
    # Set cookie for browser clients
    response.set_cookie(
        key="access_token",
        value=f"Bearer {access_token}",
        httponly=True,
        max_age=auth.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        samesite="lax",
        secure=False # Set to True in production with HTTPS
    )
    
    return {"access_token": access_token, "token_type": "bearer"}

@router.post("/token", response_model=schemas.Token)
def login_for_access_token(
    response: Response,
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(database.get_db)
):
    """
    OAuth2 compatible token login, get an access token for future requests.
    This endpoint is used by the Swagger UI for authentication.
    """
    user = db.query(models.User).filter(models.User.username == form_data.username).first()
    if not user or not auth.verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    access_token_expires = timedelta(minutes=auth.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = auth.create_access_token(
        data={"sub": user.username}, expires_delta=access_token_expires
    )
    
    # Set cookie for browser clients
    response.set_cookie(
        key="access_token",
        value=f"Bearer {access_token}",
        httponly=True,
        max_age=auth.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        samesite="lax",
        secure=False # Set to True in production with HTTPS
    )
    
    return {"access_token": access_token, "token_type": "bearer"}

async def get_current_user(
    db: Session = Depends(database.get_db),
    username: str = Depends(auth.get_current_user),
    access_token: Optional[str] = Cookie(None)
):
    """
    Get the current authenticated user.
    
    This uses the token authentication from security.py first (for API/Swagger clients)
    but also supports cookie-based auth for browser clients.
    """
    # First, try to get user from standard Bearer token authentication
    user = db.query(models.User).filter(models.User.username == username).first()
    
    # If not found but we have a cookie token, try that as fallback for browser clients
    if user is None and access_token:
        try:
            scheme, cookie_token = access_token.split()
            if scheme.lower() == "bearer":
                payload = auth.decode_access_token(cookie_token)
                if payload:
                    cookie_username = payload.get("sub")
                    if cookie_username:
                        user = db.query(models.User).filter(
                            models.User.username == cookie_username
                        ).first()
        except (ValueError, AttributeError):
            pass
    
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

@router.post("/logout")
def logout(response: Response):
    """
    Logout a user by removing the authentication cookie.
    Note: For API clients using Bearer tokens, the token remains valid until it expires.
    """
    response.delete_cookie("access_token")
    return {"message": "Logged out successfully"}
