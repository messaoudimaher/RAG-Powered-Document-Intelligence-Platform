import os
import sqlite3
import hashlib
import secrets
import logging
from datetime import datetime, timedelta
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from app.config import settings

logger = logging.getLogger("cogniflow.auth")

DATABASE_PATH = os.path.join(os.path.dirname(settings.chroma_persist_dir), "users.db")
security = HTTPBearer(auto_error=False)

def init_auth_db():
    """
    Initializes the SQLite user database table.
    """
    conn = None
    try:
        os.makedirs(os.path.dirname(DATABASE_PATH), exist_ok=True)
        conn = sqlite3.connect(DATABASE_PATH)
        cursor = conn.cursor()
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                username TEXT PRIMARY KEY,
                password_hash TEXT NOT NULL,
                salt TEXT NOT NULL
            )
            """
        )
        conn.commit()
        logger.info(f"Initialized auth SQLite database successfully at: {DATABASE_PATH}")
    except Exception as e:
        logger.error(f"Failed to initialize SQLite auth database: {e}")
        raise
    finally:
        if conn:
            conn.close()


def hash_password(password: str) -> tuple[str, str]:
    """
    Hashes a password with a secure randomly generated salt.
    """
    salt = secrets.token_hex(16)
    password_hash = hashlib.sha256((password + salt).encode("utf-8")).hexdigest()
    return password_hash, salt


def verify_password(password: str, password_hash: str, salt: str) -> bool:
    """
    Verifies a password against a hash using the salt.
    """
    expected_hash = hashlib.sha256((password + salt).encode("utf-8")).hexdigest()
    return secrets.compare_digest(password_hash, expected_hash)


def create_user(username: str, password: str) -> bool:
    """
    Creates a new user inside the SQLite database.
    """
    username_clean = username.strip()
    if not username_clean or len(username_clean) < 3:
        logger.warning(f"Registration failed: invalid or too short username '{username_clean}'")
        return False
    if not password or len(password) < 4:
        logger.warning(f"Registration failed: password too short for '{username_clean}'")
        return False

    conn = None
    try:
        conn = sqlite3.connect(DATABASE_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT 1 FROM users WHERE username = ?", (username_clean,))
        if cursor.fetchone():
            return False

        password_hash, salt = hash_password(password)
        cursor.execute(
            "INSERT INTO users (username, password_hash, salt) VALUES (?, ?, ?)",
            (username_clean, password_hash, salt)
        )
        conn.commit()
        return True
    except Exception as e:
        logger.error(f"Error during create_user operation: {e}")
        return False
    finally:
        if conn:
            conn.close()


def authenticate_user(username: str, password: str) -> bool:
    """
    Validates user credentials against stored hash.
    """
    username_clean = username.strip()
    if not username_clean or not password:
        return False

    conn = None
    try:
        conn = sqlite3.connect(DATABASE_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT password_hash, salt FROM users WHERE username = ?", (username_clean,))
        row = cursor.fetchone()
        if not row:
            return False
        
        password_hash, salt = row
        return verify_password(password, password_hash, salt)
    except Exception as e:
        logger.error(f"Error during authenticate_user: {e}")
        return False
    finally:
        if conn:
            conn.close()


def create_access_token(data: dict, expires_delta: timedelta | None = None) -> str:
    """
    Encodes standard HS256 JWT access token.
    """
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=settings.jwt_access_token_expire_minutes)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)
    return encoded_jwt


async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> str:
    """
    FastAPI security dependency validating JWT. Returns username.
    """
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing Authorization token.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    token = credentials.credentials
    try:
        payload = jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
        username: str = payload.get("sub")
        if username is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token contents: missing sub claim.",
                headers={"WWW-Authenticate": "Bearer"},
            )
        return username
    except jwt.PyJWTError as e:
        logger.warning(f"Failed JWT validation attempt: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid or expired security token: {e}",
            headers={"WWW-Authenticate": "Bearer"},
        )
