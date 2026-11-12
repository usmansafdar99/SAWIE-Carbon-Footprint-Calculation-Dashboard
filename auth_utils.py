"""JWT and password helpers"""
import os
from datetime import datetime, timedelta
from typing import Optional

from jose import JWTError, jwt
from passlib.context import CryptContext
from dotenv import load_dotenv

load_dotenv()

SECRET_KEY = os.getenv("SECRET_KEY", "carbonlens-secret-change-in-production")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 12 * 60          # normal session: 12 hours
REMEMBER_TOKEN_EXPIRE_MINUTES = 7 * 24 * 60    # "keep me signed in": 7 days

# Session cookie. HttpOnly so page scripts can never read the token.
AUTH_COOKIE_NAME = "cl_session"

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=15))
    to_encode["exp"] = expire
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def set_auth_cookie(response, token: str, remember: bool, secure: bool):
    """Attach the JWT to the response as an HttpOnly, SameSite=Lax cookie."""
    response.set_cookie(
        AUTH_COOKIE_NAME,
        token,
        max_age=(REMEMBER_TOKEN_EXPIRE_MINUTES * 60) if remember else None,
        httponly=True,
        secure=secure,
        samesite="Lax",
        path="/",
    )
    return response


def clear_auth_cookie(response):
    response.delete_cookie(AUTH_COOKIE_NAME, path="/", samesite="Lax")
    return response


def token_from_request(req) -> Optional[str]:
    """Cookie first; an Authorization: Bearer header is still accepted for API clients."""
    token = req.cookies.get(AUTH_COOKIE_NAME)
    if token:
        return token
    auth = req.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        return auth.split(" ", 1)[1].strip() or None
    return None


def decode_token(token: str) -> Optional[str]:
    """Return username string or None if invalid."""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload.get("sub")
    except JWTError:
        return None
