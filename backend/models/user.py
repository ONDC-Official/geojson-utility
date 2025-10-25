from sqlalchemy import Column, Integer, String, DateTime, func
from db.session import Base
import os

class User(Base):
    __tablename__ = 'users'
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    token = Column(String, nullable=True)
    lepton_token_limit = Column(Integer, default=lambda: int(os.getenv("DEFAULT_USER_TOKENS", 20)), nullable=False)
    lepton_tokens_used = Column(Integer, default=0, nullable=False)
    created_at = Column(DateTime, default=func.now())
    
    # Download tracking
    total_csvs_downloaded = Column(Integer, default=0, nullable=False)
    last_csv_download_at = Column(DateTime, nullable=True) 