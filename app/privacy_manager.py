from app.models import User, Consent, Session
from sqlalchemy.orm import Session as DBSession
from datetime import datetime, timedelta

class PrivacyManager:
    def __init__(self, db: DBSession):
        self.db = db

    def schedule_deletion(self, user: User):
        # Mark user for deletion (e.g., set is_active=False, add deletion timestamp)
        user.is_active = False
        user.deletion_scheduled_at = datetime.utcnow()  # Add this field to model if needed
        # Revoke consents
        consents = self.db.query(Consent).filter_by(user_id=user.user_id, revoked_at=None).all()
        for consent in consents:
            consent.revoked_at = datetime.utcnow()
        self.db.commit()

    def erase_user(self, user: User):
        # Hard delete PII & expenses after grace period
        # Delete user, consents, sessions, expenses, budgets, aliases, messages
        self.db.query(Session).filter_by(user_id=user.user_id).delete()
        self.db.query(Consent).filter_by(user_id=user.user_id).delete()
        # Add deletes for expenses, budgets, aliases, messages as needed
        self.db.query(User).filter_by(user_id=user.user_id).delete()
        self.db.commit()

    def export_user(self, user: User, month: str = None):
        # Generate CSV, return signed URL (stub)
        # Query expenses for user, filter by month if provided
        # Generate CSV, upload to storage, return signed URL
        return "https://example.com/download/yourfile.csv"

    def log_sar(self, user: User):
        # Log subject access request as message (stub)
        pass
