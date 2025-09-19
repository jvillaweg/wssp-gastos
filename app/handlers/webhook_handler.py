import json
from fastapi import Request, HTTPException
from pydantic import ValidationError
from app.handlers.message_handler import MessageHandler
from app.webhooks.models import WhatsAppWebhookEvent, MessageEvent


class WebhookHandler:
    """Handles WhatsApp webhook processing."""
    
    def __init__(self, db):
        self.db = db
        self.message_handler = MessageHandler(db)
    
    def process_webhook(self, event_data: dict) -> dict:
        """Process a WhatsApp webhook event."""
        try:
            webhook_event = WhatsAppWebhookEvent(**event_data)
            
            for message_data in webhook_event.get_message_events():
                message_event = MessageEvent(**message_data)
                self.message_handler.handle(message_event, raw_payload=event_data)
                
            return {"status": "ok"}
            
        except ValidationError as e:
            print(f"Validation error parsing webhook data: {e}")
            raise HTTPException(status_code=400, detail=f"Invalid webhook data: {e}")
        except Exception as e:
            import traceback
            print(f"Unexpected error processing webhook: {e}")
            print(f"Full traceback: {traceback.format_exc()}")
            raise HTTPException(status_code=500, detail="Internal server error")
