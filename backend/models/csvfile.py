from sqlalchemy import Column, Integer, String, LargeBinary, DateTime, func
from db.session import Base

class CSVFile(Base):
    __tablename__ = 'csv_files'
    id = Column(Integer, primary_key=True, index=True)
    filename = Column(String, index=True)
    file_content = Column(LargeBinary)
    username = Column(String, index=True, nullable=True)
    user_id = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=func.now())
    status = Column(String, default='pending', nullable=False)
    error = Column(String, nullable=True) 