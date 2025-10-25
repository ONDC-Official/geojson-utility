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
    
    # Processing metrics
    total_rows = Column(Integer, nullable=True)
    successful_rows = Column(Integer, nullable=True)
    failed_rows = Column(Integer, nullable=True)
    
    # Timing data
    processing_started_at = Column(DateTime, nullable=True)
    processing_completed_at = Column(DateTime, nullable=True)
    processing_duration_seconds = Column(Integer, nullable=True)
    
    # Download tracking
    download_count = Column(Integer, default=0, nullable=False)
    last_downloaded_at = Column(DateTime, nullable=True)
    first_downloaded_at = Column(DateTime, nullable=True)
    
    # API usage tracking
    lepton_api_calls_made = Column(Integer, nullable=True)
    tokens_consumed = Column(Integer, nullable=True) 