from datetime import UTC, datetime, timedelta

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError

from app.config import get_settings

# Fixed rather than configurable so a token can never choose its own algorithm.
JWT_ALGORITHM = "HS256"

MIN_USER_ID = 1
MAX_USER_ID = 2_147_483_647

# Argon2id with the library's recommended parameters.
password_hasher = PasswordHasher()


def hash_password(password: str) -> str:
    return password_hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return password_hasher.verify(password_hash, password)
    except (VerificationError, InvalidHashError):
        return False


def create_access_token(user_id: int) -> str:
    settings = get_settings()
    issued_at = datetime.now(UTC)
    claims = {
        "sub": str(user_id),
        "iat": issued_at,
        "exp": issued_at + timedelta(minutes=settings.access_token_expire_minutes),
    }
    return jwt.encode(claims, settings.jwt_secret_key.get_secret_value(), algorithm=JWT_ALGORITHM)


def decode_access_token(token: str) -> int | None:
    """Return the user id carried by a valid, unexpired token, otherwise None."""
    try:
        claims = jwt.decode(
            token,
            get_settings().jwt_secret_key.get_secret_value(),
            algorithms=[JWT_ALGORITHM],
            options={"require": ["sub", "exp"]},
        )
        user_id = int(claims["sub"])
    except (jwt.InvalidTokenError, ValueError):
        return None
    # Ids are PostgreSQL integers. Anything outside that range cannot be a
    # user and is refused here rather than reaching the database.
    if not MIN_USER_ID <= user_id <= MAX_USER_ID:
        return None
    return user_id
