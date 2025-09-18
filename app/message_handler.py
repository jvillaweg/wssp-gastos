from app.message_parser import MessageStrategy
from app.rate_limiter import RateLimiter
from app.models import Expense, User
from app.wa_sender import WhatsAppSender
from app.webhook_events import MessageEvent

class MessageHandler:
    def __init__(self, db):
        self.db = db
        self.rate_limiter = RateLimiter()

    def handle(self, event: MessageEvent):
        from datetime import datetime, timezone
        phoneNumber = event.from_
        message_id = event.message_id
        text: str = event.text
        # Lookup/create user
        user = self.get_or_create_user(phoneNumber)
        if not self.rate_limiter.check(user.id):
            WhatsAppSender.send_message(phoneNumber, "Demasiados mensajes. Espera un momento.")
            return
        # Blocked
        if user.is_blocked:
            WhatsAppSender.send_message(phoneNumber, "Tu acceso está bloqueado. Contacta soporte.")
            return
        # Update last_seen_at
        user.last_seen_at = datetime.now(timezone.utc)
        self.db.commit()

        response = MessageStrategy(user).handle_message(text)
        WhatsAppSender.send_message(phoneNumber, response)

    def get_or_create_user(self, phoneNumber):
        user = self.db.query(User).filter_by(phone=phoneNumber).first()
        if not user:
            user = User(phone=phoneNumber)
            self.db.add(user)
            self.db.commit()
        return user

