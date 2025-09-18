import os
import logging
from mangum import Mangum

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Import FastAPI app (this should be fast)
from app.main import app

# Optional: Run migrations only if explicitly requested
if os.getenv("RUN_MIGRATIONS_ON_START", "false").lower() == "true":
    def run_migrations():
        """Run database migrations on Lambda startup"""
        try:
            from alembic.config import Config
            from alembic import command
            
            if not os.getenv("DATABASE_URL"):
                logger.warning("DATABASE_URL not found, skipping migrations")
                return
                
            logger.info("Running database migrations...")
            alembic_cfg = Config("alembic.ini")
            alembic_cfg.set_main_option("sqlalchemy.url", os.getenv("DATABASE_URL"))
            command.upgrade(alembic_cfg, "head")
            logger.info("✅ Database migrations completed successfully!")
            
        except Exception as e:
            logger.error(f"❌ Migration failed: {e}")
            
    # Run migrations on cold start only if requested
    run_migrations()

# Wrap FastAPI app for Lambda
handler = Mangum(app, lifespan="off")  # Disable lifespan for faster startup
