#!/usr/bin/env python3
"""
Database migration runner script
"""
import os
import sys
from alembic.config import Config
from alembic import command
from dotenv import load_dotenv

def run_migrations():
    """Run pending database migrations"""
    # Load environment variables from .env file
    load_dotenv()
    
    # Set up Alembic config
    alembic_cfg = Config("alembic.ini")
    
    # Override database URL if provided via environment
    if os.getenv("DATABASE_URL"):
        alembic_cfg.set_main_option("sqlalchemy.url", os.getenv("DATABASE_URL"))
        print(f"Using database: {os.getenv('DATABASE_URL')}")
    
    try:
        print("Running database migrations...")
        command.upgrade(alembic_cfg, "head")
        print("✅ Migrations completed successfully!")
    except Exception as e:
        print(f"❌ Migration failed: {e}")
        sys.exit(1)


#alembic revision --autogenerate -m "description of change"
# python migrate.py

if __name__ == "__main__":
    run_migrations()
