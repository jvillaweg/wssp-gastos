from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import OperationalError
import os
import time
import logging
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Database connection with connection pooling for Lambda
DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    raise ValueError("DATABASE_URL environment variable is not set")

# Check if running locally vs Lambda
is_lambda = os.getenv("AWS_LAMBDA_FUNCTION_NAME") is not None

if is_lambda:
    # Optimized for Lambda - smaller pool, shorter timeouts
    engine = create_engine(
        DATABASE_URL,
        pool_size=1,
        max_overflow=0,
        pool_timeout=10,
        pool_recycle=300,      # 5 minutes for Lambda
        pool_pre_ping=True,
        connect_args={
            "connect_timeout": 10,
            "application_name": "wssp-lambda",
            "sslmode": "require"  # Ensure SSL connection
        }
    )
else:
    # Optimized for local development - persistent connections
    engine = create_engine(
        DATABASE_URL,
        pool_size=5,
        max_overflow=10,
        pool_timeout=30,
        pool_recycle=1800,  # 30 minutes
        pool_pre_ping=True,
        echo=False  # Set to True for SQL debugging
    )

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)



def get_db():
    """Get database session - relies on pool_pre_ping for connection validation."""
    db = SessionLocal()
    try:
        yield db
    except Exception as e:
        logging.error(f"Database error: {e}")
        raise
    finally:
        db.close()
