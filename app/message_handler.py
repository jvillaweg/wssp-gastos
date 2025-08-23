from fastapi import Request
from app.session_manager import SessionManager
from app.command_router import CommandRouter
from app.rate_limiter import RateLimiter
from app.idempotency import IdempotencyManager
from app.privacy_manager import PrivacyManager
from app.models import User, Session

class MessageHandler:
    def __init__(self, db):
        self.db = db
        self.session_manager = SessionManager(db)
        self.command_router = CommandRouter(db)
        self.rate_limiter = RateLimiter()
        self.idempotency = IdempotencyManager(db)
        self.privacy = PrivacyManager(db)

    def handle(self, event):
        from datetime import datetime
        phone_e164 = event.get("from")
        message_id = event.get("message_id")
        text = event.get("text")
        # Lookup/create user
        user = self.get_or_create_user(phone_e164)
        # Idempotency check
        if self.idempotency.is_duplicate(message_id):
            return
        self.idempotency.mark_processed(message_id)
        # Rate limiting
        if not self.rate_limiter.check(user.user_id):
            self.session_manager.send_message(phone_e164, "Demasiados mensajes. Espera un momento.")
            return
        # Blocked
        if user.is_blocked:
            self.session_manager.send_message(phone_e164, "Tu acceso está bloqueado. Contacta soporte.")
            return
        # Update last_seen_at
        user.last_seen_at = datetime.utcnow()
        self.db.commit()
        # Session
        session = self.get_or_create_session(user)
        if session.state and session.state.startswith("ONBOARDING"):
            self.session_manager.handle_onboarding(user, session, text)
        elif text.lower().split()[0] in ["help", "profile", "set", "erase", "export", "stop", "start", "block", "unblock", "stats"]:
            self.command_router.handle_command(user, session, text)
        else:
            # Expense parser or fallback
            self.session_manager.send_message(phone_e164, "No entiendo. Escribe 'help' para ver comandos.")

    def get_or_create_user(self, phone_e164):
        from datetime import datetime
        user = self.db.query(User).filter_by(phone_e164=phone_e164).first()
        if not user:
            user = User(phone_e164=phone_e164, created_at=datetime.utcnow(), is_active=True, is_blocked=False)
            self.db.add(user)
            self.db.commit()
        return user

    def get_or_create_session(self, user):
        from datetime import datetime
        session = self.db.query(Session).filter_by(user_id=user.user_id).first()
        if not session:
            session = Session(user_id=user.user_id, state="NEW", started_at=datetime.utcnow(), updated_at=datetime.utcnow())
            self.db.add(session)
            self.db.commit()
        return session
