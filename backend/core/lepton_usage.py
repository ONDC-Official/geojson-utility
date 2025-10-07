from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from models.user import User
import logging

logger = logging.getLogger(__name__)

class LeptonTokenService:
    """Service for managing Lepton API token consumption per user."""
    
    @staticmethod
    def check_user_has_tokens(user_id: int, db: Session) -> bool:
        """
        Check if user has any tokens available (non-consuming check).
        
        Args:
            user_id: The user's database ID
            db: Database session
            
        Returns:
            True if user has tokens available, False otherwise
        """
        try:
            user = db.query(User).filter(User.id == user_id).first()
            if not user:
                logger.warning(f"User {user_id} not found when checking token availability")
                return False
            
            available_tokens = user.lepton_token_limit - user.lepton_tokens_used
            return available_tokens > 0
            
        except SQLAlchemyError as e:
            logger.error(f"Database error checking tokens for user {user_id}: {e}")
            return False
    
    @staticmethod
    def consume_token_after_success(user_id: int, db: Session) -> bool:
        """
        Atomically consume one token AFTER successful API call.
        Uses row-level locking to prevent race conditions.
        
        Args:
            user_id: The user's database ID
            db: Database session
            
        Returns:
            True if token was successfully consumed, False if no tokens available
        """
        try:
            # Use SELECT ... FOR UPDATE to lock the user row
            user = db.query(User).filter(User.id == user_id).with_for_update().first()
            
            if not user:
                logger.warning(f"User {user_id} not found when consuming token")
                return False
            
            # Check if user still has tokens available
            if user.lepton_tokens_used >= user.lepton_token_limit:
                logger.info(f"User {user_id} has no tokens remaining ({user.lepton_tokens_used}/{user.lepton_token_limit})")
                return False
            
            # Consume one token
            user.lepton_tokens_used += 1
            db.commit()
            
            logger.info(f"Token consumed for user {user_id}. Usage: {user.lepton_tokens_used}/{user.lepton_token_limit}")
            return True
            
        except SQLAlchemyError as e:
            logger.error(f"Database error consuming token for user {user_id}: {e}")
            db.rollback()
            return False
    
    @staticmethod 
    def get_token_status(user_id: int, db: Session) -> dict:
        """
        Get user's current token status for display.
        
        Args:
            user_id: The user's database ID
            db: Database session
            
        Returns:
            Dictionary with 'used', 'limit', and 'remaining' token counts
        """
        try:
            user = db.query(User).filter(User.id == user_id).first()
            
            if not user:
                logger.warning(f"User {user_id} not found when getting token status")
                return {"used": 0, "limit": 0, "remaining": 0}
            
            remaining = max(0, user.lepton_token_limit - user.lepton_tokens_used)
            
            return {
                "used": user.lepton_tokens_used,
                "limit": user.lepton_token_limit,
                "remaining": remaining
            }
            
        except SQLAlchemyError as e:
            logger.error(f"Database error getting token status for user {user_id}: {e}")
            return {"used": 0, "limit": 0, "remaining": 0}
    
    @staticmethod
    def get_user_token_info(user_id: int, db: Session) -> tuple:
        """
        Get user's token limit and usage for internal calculations.
        
        Args:
            user_id: The user's database ID
            db: Database session
            
        Returns:
            Tuple of (tokens_used, token_limit, remaining)
        """
        try:
            user = db.query(User).filter(User.id == user_id).first()
            
            if not user:
                return (0, 0, 0)
            
            remaining = max(0, user.lepton_token_limit - user.lepton_tokens_used)
            return (user.lepton_tokens_used, user.lepton_token_limit, remaining)
            
        except SQLAlchemyError as e:
            logger.error(f"Database error getting token info for user {user_id}: {e}")
            return (0, 0, 0)