from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..auth import create_access_token, get_current_user, hash_password, verify_password
from ..database import get_db
from ..models import User
from ..schemas import CurrentUserResponse, TokenResponse, UserCreate, UserResponse

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


@router.get("/health")
def auth_health() -> dict[str, str]:
    return {"message": "Auth service is running"}


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a user",
)
def register_user(payload: UserCreate, db: Session = Depends(get_db)) -> User:
    existing_user = db.scalar(select(User).where(User.email == payload.email))
    if existing_user is not None:
        raise HTTPException(status_code=409, detail="An account with this email already exists")

    user = User(name=payload.name, email=str(payload.email), password_hash=hash_password(payload.password))
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.post("/login", response_model=TokenResponse, summary="Log in and receive a JWT")
def login(
    form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)
) -> dict[str, str]:
    user = db.scalar(select(User).where(User.email == form_data.username))
    if user is None or not verify_password(form_data.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return {"access_token": create_access_token(user.id), "token_type": "bearer"}


@router.get("/me", response_model=CurrentUserResponse, summary="Get the authenticated user")
def read_current_user(current_user: User = Depends(get_current_user)) -> User:
    return current_user
