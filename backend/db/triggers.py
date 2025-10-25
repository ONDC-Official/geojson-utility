"""
PostgreSQL trigger setup for CSV status notifications
"""
import logging
from sqlalchemy import text
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

# PostgreSQL trigger function for CSV status notifications
TRIGGER_FUNCTION_SQL = """
CREATE OR REPLACE FUNCTION notify_csv_status_change()
RETURNS TRIGGER AS $$
BEGIN
    -- Only notify on status changes or when status is first set
    IF (NEW.status != OLD.status) OR (OLD.status IS NULL AND NEW.status IS NOT NULL) THEN
        PERFORM pg_notify('csv_status_change', 
            json_build_object(
                'csv_id', NEW.id,
                'status', NEW.status,
                'event_type', CASE 
                    WHEN NEW.status = 'processing' THEN 'start'
                    WHEN NEW.status IN ('done', 'failed', 'partial') THEN 'complete'
                    ELSE 'update'
                END,
                'successful_rows', NEW.successful_rows,
                'failed_rows', NEW.failed_rows,
                'total_rows', NEW.total_rows,
                'error', NEW.error
            )::text
        );
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;
"""

# PostgreSQL trigger on csv_files table
TRIGGER_SQL = """
DROP TRIGGER IF EXISTS csv_status_trigger ON csv_files;
CREATE TRIGGER csv_status_trigger
    AFTER INSERT OR UPDATE ON csv_files
    FOR EACH ROW
    EXECUTE FUNCTION notify_csv_status_change();
"""

def setup_postgresql_triggers(db: Session):
    """Setup PostgreSQL triggers for CSV status notifications"""
    try:
        logger.info("Setting up PostgreSQL triggers for CSV status notifications")
        
        # Create the trigger function
        db.execute(text(TRIGGER_FUNCTION_SQL))
        logger.info("Created PostgreSQL trigger function: notify_csv_status_change()")
        
        # Create the trigger
        db.execute(text(TRIGGER_SQL))
        logger.info("Created PostgreSQL trigger: csv_status_trigger")
        
        db.commit()
        logger.info("PostgreSQL triggers setup completed successfully")
        
    except Exception as e:
        logger.error(f"Failed to setup PostgreSQL triggers: {e}")
        db.rollback()
        raise

def check_triggers_exist(db: Session) -> bool:
    """Check if PostgreSQL triggers are properly set up"""
    try:
        # Check if trigger function exists
        result = db.execute(text("""
            SELECT EXISTS (
                SELECT 1 FROM pg_proc 
                WHERE proname = 'notify_csv_status_change'
            );
        """)).scalar()
        
        if not result:
            return False
        
        # Check if trigger exists
        result = db.execute(text("""
            SELECT EXISTS (
                SELECT 1 FROM pg_trigger 
                WHERE tgname = 'csv_status_trigger'
            );
        """)).scalar()
        
        return bool(result)
        
    except Exception as e:
        logger.error(f"Failed to check triggers: {e}")
        return False