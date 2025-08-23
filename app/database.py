from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import os

# Database connection with connection pooling for Lambda
DATABASE_URL = os.getenv("DATABASE_URL")

# Optimized for Lambda - smaller pool, shorter timeouts
engine = create_engine(
    DATABASE_URL,
    pool_size=1,
    max_overflow=0,
    pool_timeout=10,
    pool_recycle=3600,
    pool_pre_ping=True
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
