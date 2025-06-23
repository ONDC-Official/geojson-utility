from sqlalchemy import Column, Integer, String, DateTime, func
from db.session import Base

class UserToken(Base):
    __tablename__ = 'user_tokens'
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, index=True)
    token = Column(String, nullable=False)
    created_at = Column(DateTime, default=func.now()) 