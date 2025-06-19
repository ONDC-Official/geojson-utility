from datetime import datetime, timedelta
from fastapi import Depends, HTTPException, status, APIRouter
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import jwt, JWTError
from sqlalchemy.orm import Session, sessionmaker
from db.session import get_db
from models.jwt_blacklist_sqlite import JWTBlacklistSQLite, SQLiteBase
import uuid
import os
from dotenv import load_dotenv
from sqlalchemy import create_engine, func as sa_func

load_dotenv()

SECRET_KEY = os.environ["SECRET_KEY"]
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.environ.get("ACCESS_TOKEN_EXPIRE_MINUTES", 30))
security = HTTPBearer()

# SQLite setup for JWT blacklist
token_blacklist_engine = create_engine("sqlite:///jwt_blacklist.db")
SQLiteBase.metadata.create_all(bind=token_blacklist_engine)
TokenBlacklistSession = sessionmaker(autocommit=False, autoflush=False, bind=token_blacklist_engine)

def create_access_token(data: dict, expires_delta: timedelta = None):
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    jti = str(uuid.uuid4())
    to_encode.update({"exp": expire, "jti": jti})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt, jti

def blacklist_jwt(jti: str, db: Session = None):
    session = TokenBlacklistSession()
    session.add(JWTBlacklistSQLite(jti=jti))
    session.commit()
    session.close()

def is_token_blacklisted(jti: str, db: Session = None) -> bool:
    session = TokenBlacklistSession()
    result = session.query(JWTBlacklistSQLite).filter(JWTBlacklistSQLite.jti == jti).first() is not None
    session.close()
    return result

def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security), db: Session = Depends(get_db)):
    token = credentials.credentials
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        jti = payload.get("jti")
        if is_token_blacklisted(jti):
            raise HTTPException(status_code=401, detail="Token has been revoked")
        username = payload.get("sub")
        if username is None:
            raise HTTPException(status_code=401, detail="Invalid token payload")
        return {"username": username, "jti": jti}
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")

admin_router = APIRouter(prefix="/admin", tags=["admin"])

def cleanup_expired_blacklist_entries():
    session = TokenBlacklistSession()
    cutoff = datetime.utcnow() - timedelta(days=7)
    deleted = session.query(JWTBlacklistSQLite).filter(JWTBlacklistSQLite.created_at < cutoff).delete()
    session.commit()
    session.close()
    return deleted

@admin_router.post("/cleanup-blacklist")
def cleanup_blacklist_endpoint():
    deleted = cleanup_expired_blacklist_entries()
    return {"deleted": deleted} 