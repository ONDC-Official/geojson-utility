from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session
from schemas.user import UserCreate, UserRead, UserLogin
from schemas.token import Token
from crud.user import get_user_by_username, create_user, authenticate_user, delete_user_by_username
from core.auth import create_access_token, get_current_user
from db.session import get_db
from core.limiter import limiter
from fastapi.security import HTTPAuthorizationCredentials
from typing import Optional
from models.user_token import UserToken

router = APIRouter(prefix="/auth", tags=["auth"])

@router.post("/register")
def register(user: UserCreate, db: Session = Depends(get_db)):
    db_user = get_user_by_username(db, user.username)
    if db_user:
        raise HTTPException(status_code=400, detail="Username already registered")
    created_user = create_user(db, user.username, user.password)
    access_token, jti = create_access_token(data={"sub": created_user.username})
    # Save the token in the database
    db_token = UserToken(username=created_user.username, token=access_token)
    db.add(db_token)
    db.commit()
    return {"access_token": access_token, "token_type": "bearer"}

@router.post("/login")
@limiter.limit("5/minute")
async def login(request: Request, token: Optional[str] = None):
    # Accept JWT token in the request body as {"token": "..."}
    if not token:
        try:
            body = await request.json()
            token = body.get("token")
        except Exception:
            raise HTTPException(status_code=400, detail="Token required in request body.")
    if not token:
        raise HTTPException(status_code=400, detail="Token required in request body.")
    credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)
    user = get_current_user(credentials)
    return {"username": user["username"]}

@router.post("/logout")
def logout(current_user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    try:
        # Only delete user from database
        username = current_user['username']
        delete_user_by_username(db, username)
        return {"msg": "Logged out successfully and user deleted"}
    except Exception:
        raise HTTPException(status_code=500, detail="Error deleting user") 