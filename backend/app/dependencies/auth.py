from collections.abc import Callable
from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.database import DatabaseSession
from app.models.user import User, UserRole
from app.services.security import decode_access_token

# auto_error is off so a missing header produces the same 401 as a bad token.
bearer_scheme = HTTPBearer(auto_error=False)


def _unauthenticated() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Not authenticated",
        headers={"WWW-Authenticate": "Bearer"},
    )


def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
    db: DatabaseSession,
) -> User:
    if credentials is None:
        raise _unauthenticated()

    user_id = decode_access_token(credentials.credentials)
    if user_id is None:
        raise _unauthenticated()

    # Loaded on every request so a deleted account, or a changed role, takes
    # effect immediately instead of when the token expires.
    user = db.get(User, user_id)
    if user is None:
        raise _unauthenticated()
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def require_role(*allowed_roles: UserRole) -> Callable[[User], User]:
    """Build a dependency that admits only users holding one of the given roles."""

    def check_role(current_user: CurrentUser) -> User:
        if current_user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have permission to perform this action",
            )
        return current_user

    return check_role


CurrentFarmer = Annotated[User, Depends(require_role(UserRole.FARMER))]
