from fastapi import APIRouter, HTTPException, Request, status

from app.database import DatabaseSession
from app.dependencies.auth import CurrentUser
from app.models.user import User
from app.schemas.auth import AccessTokenResponse, LoginCredentials, UserRegistration
from app.schemas.user import UserRead
from app.services.auth import EmailAlreadyRegisteredError, authenticate_user, register_user
from app.services.login_throttle import login_throttle
from app.services.security import create_access_token

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=UserRead, status_code=status.HTTP_201_CREATED)
def register(registration: UserRegistration, db: DatabaseSession) -> User:
    try:
        return register_user(db, registration)
    except EmailAlreadyRegisteredError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists",
        ) from None


@router.post("/login", response_model=AccessTokenResponse)
def login(
    credentials: LoginCredentials, request: Request, db: DatabaseSession
) -> AccessTokenResponse:
    client = request.client.host if request.client else None

    # Checked before the password, so a locked-out account gives nothing away
    # even when the guess happens to be right.
    retry_after_seconds = login_throttle.seconds_until_allowed(credentials.email, client)
    if retry_after_seconds > 0:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many failed login attempts. Please wait and try again.",
            headers={"Retry-After": str(retry_after_seconds)},
        )

    user = authenticate_user(db, credentials.email, credentials.password)
    if user is None:
        login_throttle.record_failure(credentials.email, client)
        # One message for both an unknown email and a wrong password, so the
        # response does not confirm which emails are registered.
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    login_throttle.record_success(credentials.email)
    return AccessTokenResponse(
        access_token=create_access_token(user.id),
        user=UserRead.model_validate(user),
    )


@router.get("/me", response_model=UserRead)
def read_current_user(current_user: CurrentUser) -> User:
    return current_user
