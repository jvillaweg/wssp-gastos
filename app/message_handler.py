from app.message_parser import MessageStrategy
from app.rate_limiter import RateLimiter
from app.models import Expense, User, MessageLog
from app.wa_sender import WhatsAppSender
from app.webhook_events import MessageEvent

class MessageHandler:
    def __init__(self, db):
        self.db = db
        self.rate_limiter = RateLimiter()

    def handle(self, event: MessageEvent, raw_payload: dict = None):
        from datetime import datetime, timezone
        phoneNumber = event.from_
        message_id = event.message_id
        text: str = event.text
        existing_log = self.db.query(MessageLog).filter_by(
            provider="meta",
            provider_message_id=message_id
        ).first()
        
        if existing_log:
            print(f"Message {message_id} already processed, skipping...")
            return
        
        # Log the incoming message
        message_log = MessageLog(
            provider="meta",
            provider_message_id=message_id,
            chat_id=phoneNumber,
            direction="in",
            text=text,
            payload_json=raw_payload,
            status="received"
        )
        self.db.add(message_log)
        self.db.commit()
        
        try:
            # Lookup/create user
            user = self.get_or_create_user(phoneNumber)
            if not self.rate_limiter.check(user.id):
                WhatsAppSender.send_message(phoneNumber, "Demasiados mensajes. Espera un momento.")
                message_log.status = "rate_limited"
                self.db.commit()
                return
            # Blocked
            if user.is_blocked:
                WhatsAppSender.send_message(phoneNumber, "Tu acceso está bloqueado. Contacta soporte.")
                message_log.status = "blocked"
                self.db.commit()
                return
            # Update last_seen_at
            user.last_seen_at = datetime.now(timezone.utc)
            self.db.commit()

            handler = MessageStrategy(self.db, user)

            if event.type == "interactive" and event.interactive:
                handler.handle_interactive(event.interactive)
            else: 
                response = handler.handle_message(text)
                WhatsAppSender.send_message(phoneNumber, response)

            # Mark message as successfully processed
            message_log.status = "processed"
            self.db.commit()
            
        except Exception as e:
            # Mark message as failed
            message_log.status = "failed"
            message_log.error = str(e)
            self.db.commit()
            WhatsAppSender.send_message(phoneNumber, "Ocurrió un error procesando tu mensaje. Intenta nuevamente.")
            raise

    def get_or_create_user(self, phoneNumber):
        user = self.db.query(User).filter_by(phone=phoneNumber).first()
        if not user:
            user = User(phone=phoneNumber)
            self.db.add(user)
            self.db.commit()
        return user

