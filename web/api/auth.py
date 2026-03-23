"""
Authentication API router.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr, Field

from database.connection import get_session
from database.models import User
from web.auth import create_access_token, get_current_user, get_password_hash, verify_password


router = APIRouter()


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)
    full_name: str | None = Field(default=None, max_length=255)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


@router.post("/register")
async def register(payload: RegisterRequest):
    with get_session() as session:
        existing_user = session.query(User).filter(User.email == payload.email.lower()).first()
        if existing_user:
            raise HTTPException(status_code=409, detail="Email already registered")

        user = User(
            email=payload.email.lower(),
            full_name=payload.full_name,
            password_hash=get_password_hash(payload.password),
            is_active=True,
        )
        session.add(user)
        session.commit()
        session.refresh(user)

        token = create_access_token({"sub": str(user.id)})

        return {
            "access_token": token,
            "token_type": "bearer",
            "user": {
                "id": user.id,
                "email": user.email,
                "full_name": user.full_name,
            },
        }


@router.post("/login")
async def login(payload: LoginRequest):
    with get_session() as session:
        user = session.query(User).filter(User.email == payload.email.lower()).first()
        if not user or not verify_password(payload.password, user.password_hash):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password",
            )

        if not user.is_active:
            raise HTTPException(status_code=403, detail="User account is inactive")

        token = create_access_token({"sub": str(user.id)})
        return {
            "access_token": token,
            "token_type": "bearer",
            "user": {
                "id": user.id,
                "email": user.email,
                "full_name": user.full_name,
            },
        }


@router.get("/me")
async def me(current_user: User = Depends(get_current_user)):
    return {
        "id": current_user.id,
        "email": current_user.email,
        "full_name": current_user.full_name,
        "is_active": current_user.is_active,
        "created_at": current_user.created_at.isoformat(),
    }
