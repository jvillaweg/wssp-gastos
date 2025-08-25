from mangum import Mangum
from app.main import app
import os
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Run migrations on Lambda startup
def run_migrations():
    """Run database migrations on Lambda startup"""
    try:
        from alembic.config import Config
        from alembic import command
        
        # Only run migrations if DATABASE_URL is available
        if not os.getenv("DATABASE_URL"):
            logger.warning("DATABASE_URL not found, skipping migrations")
            return
            
        logger.info("Running database migrations...")
        
        # Set up Alembic config
        alembic_cfg = Config("alembic.ini")
        alembic_cfg.set_main_option("sqlalchemy.url", os.getenv("DATABASE_URL"))
        
        # Run migrations
        command.upgrade(alembic_cfg, "head")
        logger.info("✅ Database migrations completed successfully!")
        
    except Exception as e:
        logger.error(f"❌ Migration failed: {e}")
        # Don't raise - let the app start anyway for debugging
        
# Run migrations on cold start
run_migrations()

# Wrap FastAPI app for Lambda
handler = Mangum(app)
