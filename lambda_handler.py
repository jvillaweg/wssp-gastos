import os
import logging
import json
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
mangum_handler = Mangum(app, lifespan="off")  # Disable lifespan for faster startup

def handler(event, context):
    """
    Main Lambda handler that routes different event types
    """
    logger.info(f"Received event: {json.dumps(event, default=str)}")
    
    # Check if this is a CloudWatch scheduled event (warm-up ping)
    if event.get("source") == "aws.events" and event.get("detail-type") == "Scheduled Event":
        logger.info("Handling CloudWatch scheduled event (warm-up)")
        return {
            "statusCode": 200,
            "body": json.dumps({
                "message": "Lambda warmed up successfully",
                "timestamp": context.aws_request_id
            })
        }
    
    # Check if this is a test event or ping
    if event.get("httpMethod") == "GET" and event.get("path") == "/ping":
        logger.info("Handling direct ping event")
        return {
            "statusCode": 200,
            "headers": {
                "Content-Type": "application/json"
            },
            "body": json.dumps({
                "status": "warm",
                "message": "Lambda is warm",
                "requestId": context.aws_request_id
            })
        }
    
    # For all other events (API Gateway, etc.), use Mangum
    try:
        return mangum_handler(event, context)
    except Exception as e:
        logger.error(f"Error handling event with Mangum: {e}")
        logger.error(f"Event details: {json.dumps(event, default=str)}")
        
        # Return a generic error response
        return {
            "statusCode": 500,
            "headers": {
                "Content-Type": "application/json"
            },
            "body": json.dumps({
                "error": "Internal server error",
                "message": str(e)
            })
        }
