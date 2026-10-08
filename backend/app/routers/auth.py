from fastapi import APIRouter, HTTPException, status

from app.database import DatabaseSession
from app.dependencies.auth import CurrentUser
from app.models.user import User
from app.schemas.auth import AccessTokenResponse, LoginCredentials, UserRegistration
from app.schemas.user import UserRead
from app.services.auth import EmailAlreadyRegisteredError, authenticate_user, register_user
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
def login(credentials: LoginCredentials, db: DatabaseSession) -> AccessTokenResponse:
    user = authenticate_user(db, credentials.email, credentials.password)
    if user is None:
        # One message for both an unknown email and a wrong password, so the
        # response does not confirm which emails are registered.
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return AccessTokenResponse(
        access_token=create_access_token(user.id),
        user=UserRead.model_validate(user),
    )


@router.get("/me", response_model=UserRead)
def read_current_user(current_user: CurrentUser) -> User:
    return current_user
