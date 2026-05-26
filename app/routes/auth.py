from datetime import timedelta
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app import crud
from app.auth import create_access_token, verify_password
from app.config import BOOTSTRAP_FIRST_USER_AS_ADMIN
from app.deps import get_db
from app.schemas import Token, UserOut, UserRegister

router = APIRouter()

@router.post("/register", response_model=UserOut)
def register(user_in: UserRegister, db: Session = Depends(get_db)):
    existing = crud.get_user_by_username(db, username=user_in.username)
    if existing:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Username already registered")
    is_first_user = crud.count_users(db) == 0
    role = "admin" if is_first_user and BOOTSTRAP_FIRST_USER_AS_ADMIN else "user"
    user = crud.create_user(db, username=user_in.username, password=user_in.password, email=user_in.email, role=role)
    return user

@router.post("/login", response_model=Token)
async def login(request: Request, db: Session = Depends(get_db)):
    content_type = request.headers.get("content-type", "")
    if "application/x-www-form-urlencoded" in content_type or "multipart/form-data" in content_type:
        payload = await request.form()
        username = payload.get("username")
        password = payload.get("password")
    else:
        payload = await request.json()
        username = payload.get("username")
        password = payload.get("password")

    user = crud.get_user_by_username(db, username=username)
    if not user or not password or not verify_password(password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Incorrect username or password")
    if user.status != "active":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User is disabled")
    access_token = create_access_token(data={"sub": user.username, "role": user.role}, expires_delta=timedelta(minutes=60 * 24))
    return {"access_token": access_token, "token": access_token, "token_type": "bearer", "user": user}

from app.deps import get_current_user

@router.get("/me", response_model=UserOut)
def read_users_me(current_user=Depends(get_current_user)):
    return current_user
