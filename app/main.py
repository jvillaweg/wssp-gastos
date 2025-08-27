from fastapi import FastAPI, Request, HTTPException, Depends
from fastapi.responses import PlainTextResponse
from app.models import User, Consent, Session, UserRole, RoleEnum
from app.database import get_db
from app.message_handler import MessageHandler
from app.webhook_events import WhatsAppWebhookEvent, MessageEvent, StatusEvent
from sqlalchemy.orm import Session as DBSession
from datetime import datetime, timedelta
from pydantic import ValidationError
import hmac, hashlib, os, json

app = FastAPI()

VERIFY_TOKEN = os.getenv("META_VERIFY_TOKEN", "your_verify_token")
HUB_SIGNATURE_HEADER = "X-Hub-Signature-256"

def verify_signature(request: Request, body: bytes):
    signature = request.headers.get(HUB_SIGNATURE_HEADER)
    secret = os.getenv("META_APP_SECRET", "your_app_secret")
    expected = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return signature == f"sha256={expected}"

@app.get("/webhook/meta", response_class=PlainTextResponse)
async def verify_webhook(request: Request):
    """
    Handle WhatsApp webhook verification.
    Meta sends: hub.mode, hub.verify_token, hub.challenge
    """
    params = request.query_params
    
    mode = params.get("hub.mode", "")
    verify_token = params.get("hub.verify_token", "")
    challenge = params.get("hub.challenge", "")

    if mode == "subscribe" and verify_token == VERIFY_TOKEN and challenge:
        return PlainTextResponse(content=challenge, status_code=200)
    
    raise HTTPException(status_code=403, detail="Verification failed")

@app.post("/webhook/meta")
async def webhook_event(request: Request, db: DBSession = Depends(get_db)):
    body = await request.body()
    if not verify_signature(request, body):
        raise HTTPException(status_code=403, detail="Invalid signature")
    
    try:
        # Parse JSON data
        event_data = json.loads(body)
        print(f"Raw webhook data: {event_data}")
        
        # Create WhatsApp webhook event object
        webhook_event = WhatsAppWebhookEvent(**event_data)
        
        # Process message events
        for message_data in webhook_event.get_message_events():
            # Create MessageEvent object
            message_event = MessageEvent(**message_data)
            
            # Handle message
            handler = MessageHandler(db)
            # Convert back to dict format for handler compatibility
            event_dict = {
                "from": message_event.from_,
                "message_id": message_event.message_id,
                "text": message_event.text,
                "type": "message"
            }
            handler.handle(event_dict)
        
        # Process status events
        for status_data in webhook_event.get_status_events():
            # Create StatusEvent object
            status_event = StatusEvent(**status_data)
            
            print(f"Message status update: {status_event.message_id} -> {status_event.status}")
            
            # Log additional information if available
            if status_event.conversation:
                print(f"  Conversation: {status_event.conversation['id']}")
            
            if status_event.pricing:
                pricing = status_event.pricing
                print(f"  Pricing: {pricing['category']} - Billable: {pricing['billable']}")
            
            # You can add status handling logic here
            # For example, update message delivery status in database
            # handler.handle_status(status_event)
            
    except ValidationError as e:
        print(f"Validation error parsing webhook data: {e}")
        raise HTTPException(status_code=400, detail=f"Invalid webhook data: {e}")
    except json.JSONDecodeError as e:
        print(f"JSON decode error: {e}")
        raise HTTPException(status_code=400, detail="Invalid JSON data")
    except Exception as e:
        print(f"Unexpected error processing webhook: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")
    
    return {"status": "ok"}

@app.get("/healthz")
def healthz():
    return {"status": "ok"}

@app.get("/reports/summary")
def report_summary(user_id: int, range: str, db: DBSession = Depends(get_db)):
    # Get user expenses for range
    # ...existing code...
    return {"summary": "....."}

@app.get("/export/csv")
def export_csv(user_id: int, month: str = None, db: DBSession = Depends(get_db)):
    # Generate and return CSV export
    # ...existing code...
    return {"url": "signed_download_url"}
