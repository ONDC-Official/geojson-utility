from sqlalchemy.orm import Session
from models.user import User
from core.security import get_password_hash, verify_password
import os

def get_user_by_username(db: Session, username: str):
    return db.query(User).filter(User.username == username).first()

def create_user(db: Session, username: str, password: str):
    hashed_password = get_password_hash(password)
    default_tokens = int(os.getenv("DEFAULT_USER_TOKENS", 20))
    db_user = User(username=username, hashed_password=hashed_password, lepton_token_limit=default_tokens)
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user

# UNUSED - authenticate_user function is imported but never called in the codebase
# def authenticate_user(db: Session, username: str, password: str):
#     user = get_user_by_username(db, username)
#     if not user or not verify_password(password, user.hashed_password):
#         return None
#     return user

def delete_user_by_username(db: Session, username: str):
    user = get_user_by_username(db, username)
    if user:
        db.delete(user)
        db.commit() 