from app.models import User, Consent, Session
from sqlalchemy.orm import Session as DBSession
from datetime import datetime, timedelta

class IdempotencyManager:
    def __init__(self, db: DBSession):
        self.db = db

    def is_duplicate(self, message_id: str):
        # Query messages table for message_id
        ...

    def mark_processed(self, message_id: str):
        # Insert message_id into messages table
        ...
