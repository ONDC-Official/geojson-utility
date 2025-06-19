from sqlalchemy import Column, Integer, String, DateTime, func
from sqlalchemy.ext.declarative import declarative_base

SQLiteBase = declarative_base()

class JWTBlacklistSQLite(SQLiteBase):
    __tablename__ = 'jwt_blacklist'
    id = Column(Integer, primary_key=True, index=True)
    jti = Column(String, index=True)
    created_at = Column(DateTime, default=func.now()) 