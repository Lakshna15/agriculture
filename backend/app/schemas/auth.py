from typing import Annotated, Literal

from pydantic import AfterValidator, BaseModel, BeforeValidator, EmailStr, Field, StringConstraints

from app.models.user import UserRole
from app.schemas.user import UserRead


def _strip_if_text(value: object) -> object:
    return value.strip() if isinstance(value, str) else value


# Trimming and lowercasing make registration and login agree on one stored
# form, so "Ana@Example.com" and "ana@example.com" are the same account.
NormalizedEmail = Annotated[
    EmailStr,
    BeforeValidator(_strip_if_text),
    Field(max_length=254),
    AfterValidator(str.lower),
]

# Passwords are taken exactly as typed: whitespace is never trimmed. The upper
# bound caps the work a single request can ask the password hasher to do.
PASSWORD_MAX_LENGTH = 128


class UserRegistration(BaseModel):
    name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]
    email: NormalizedEmail
    password: str = Field(min_length=8, max_length=PASSWORD_MAX_LENGTH)
    # ADMIN is intentionally absent: administrators are never created through
    # the public API.
    role: Literal[UserRole.CUSTOMER, UserRole.FARMER]


class LoginCredentials(BaseModel):
    email: NormalizedEmail
    password: str = Field(min_length=1, max_length=PASSWORD_MAX_LENGTH)


class AccessTokenResponse(BaseModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"
    user: UserRead
