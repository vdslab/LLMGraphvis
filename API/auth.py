from datetime import datetime, timedelta, timezone
from typing import Annotated, Optional, Union
import os

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
import jwt
from jwt.exceptions import InvalidTokenError
from pwdlib import PasswordHash
from pwdlib.exceptions import UnknownHashError
from passlib.context import CryptContext
from sqlalchemy.orm import Session
from dotenv import load_dotenv

import models
import schemas
from database import get_db

# Load environment variables
load_dotenv()

# Password hashing configuration - pwdlib (preferred) with passlib fallback
pwd_hash = PasswordHash.recommended()
# Fallback for existing passwords hashed with passlib
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# OAuth2 configuration
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/token")

# JWT configuration
SECRET_KEY = os.getenv("SECRET_KEY")
if not SECRET_KEY:
    raise ValueError("SECRET_KEY environment variable is not set")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against a hash, supporting both pwdlib and passlib hashes."""
    try:
        # Try pwdlib first (preferred method)
        return pwd_hash.verify(plain_password, hashed_password)
    except UnknownHashError:
        # Fallback to passlib for existing users
        try:
            return pwd_context.verify(plain_password, hashed_password)
        except Exception:
            return False
    except Exception:
        return False


def get_password_hash(password: str) -> str:
    """Generate a password hash using pwdlib (preferred method)."""
    return pwd_hash.hash(password)


def get_user(db: Session, username: str) -> Optional[models.User]:
    """Get a user by username."""
    return db.query(models.User).filter(models.User.username == username).first()


def authenticate_user(db: Session, username: str, password: str) -> Optional[models.User]:
    """Authenticate a user."""
    user = get_user(db, username)
    if not user:
        return None
    if not verify_password(password, user.hashed_password):
        return None
    return user


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Create a JWT access token."""
    if not SECRET_KEY:
        raise ValueError("SECRET_KEY is not set")

    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


async def get_current_user(
    token: Annotated[str, Depends(oauth2_scheme)], db: Session = Depends(get_db)
) -> models.User:
    """Get the current authenticated user."""
    if not SECRET_KEY:
        raise ValueError("SECRET_KEY is not set")

    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        # Decode the JWT token
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: Optional[str] = payload.get("sub")
        if username is None:
            raise credentials_exception
        token_data = schemas.TokenData(username=username)
    except InvalidTokenError:
        raise credentials_exception

    # Get the user from the database
    user = get_user(db, username=token_data.username or "")
    if user is None:
        raise credentials_exception
    return user


async def get_current_active_user(
    current_user: Annotated[models.User, Depends(get_current_user)],
) -> models.User:
    """Get the current active user."""
    if not current_user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")
    return current_user


def get_current_user_from_token(token: str, db: Optional[Session] = None) -> Optional[models.User]:
    """
    WebSocketなどのDependsを使用できない場所でトークンからユーザーを取得する

    Args:
        token: JWTトークン
        db: データベースセッション（オプション）

    Returns:
        User: 認証されたユーザー、または認証失敗時はNone
    """
    if not SECRET_KEY:
        return None

    try:
        # JWTトークンをデコード
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: Optional[str] = payload.get("sub")
        if username is None:
            return None

        # データベースからユーザーを取得
        db_session = db
        close_db = False

        if db_session is None:
            from database import SessionLocal
            db_session = SessionLocal()
            close_db = True

        try:
            user = get_user(db_session, username=username)
            if user is None or not user.is_active:
                return None
            return user
        finally:
            if close_db and db_session:
                db_session.close()
    except InvalidTokenError:
        return None
    except Exception:
        return None
