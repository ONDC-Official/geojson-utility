from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session
from schemas.user import UserCreate, UserRead, UserLogin
from schemas.token import Token
from crud.user import get_user_by_username, create_user, authenticate_user
from core.auth import create_access_token, get_current_user, blacklist_jwt
from db.session import get_db
from core.limiter import limiter

router = APIRouter(prefix="/auth", tags=["auth"])

@router.post("/register", response_model=UserRead)
def register(user: UserCreate, db: Session = Depends(get_db)):
    db_user = get_user_by_username(db, user.username)
    if db_user:
        raise HTTPException(status_code=400, detail="Username already registered")
    return create_user(db, user.username, user.password)

@router.post("/login", response_model=Token)
@limiter.limit("5/minute")
def login(request: Request, user_credentials: UserLogin, db: Session = Depends(get_db)):
    user = authenticate_user(db, user_credentials.username, user_credentials.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token, jti = create_access_token(data={"sub": user.username})
    return {"access_token": access_token, "token_type": "bearer"}

@router.post("/logout")
def logout(current_user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    try:
        jti = current_user['jti']
        blacklist_jwt(jti, db)
        return {"msg": "Logged out successfully"}
    except Exception:
        raise HTTPException(status_code=500, detail="Error blacklisting JWT") 