from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app import crud
from app.deps import get_current_user, get_db, require_admin
from app.schemas import UserCreate, UserOut, UserUpdate

router = APIRouter()


@router.get("/", response_model=List[UserOut])
def list_users(skip: int = 0, limit: int = 100, db: Session = Depends(get_db), current_user=Depends(require_admin)):
    return crud.list_users(db, skip=skip, limit=limit)


@router.post("/", response_model=UserOut)
def create_user(user_in: UserCreate, db: Session = Depends(get_db), current_user=Depends(require_admin)):
    existing = crud.get_user_by_username(db, username=user_in.username)
    if existing:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Username already registered")
    return crud.create_user(
        db,
        username=user_in.username,
        password=user_in.password,
        email=user_in.email,
        role=user_in.role,
    )


@router.put("/{user_id}", response_model=UserOut)
def update_user(
    user_id: int,
    user_in: UserUpdate,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    user = crud.get_user(db, user_id=user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    updates = user_in.dict(exclude_unset=True)
    if current_user.role != "admin":
        if current_user.id != user_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized")
        updates.pop("role", None)
        updates.pop("status", None)

    return crud.update_user(db, user=user, updates=updates)
