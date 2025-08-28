from fastapi import FastAPI, Request, HTTPException, Depends
from fastapi.responses import PlainTextResponse
from app.database import get_db
from app.message_handler import MessageHandler
from app.webhook_events import WhatsAppWebhookEvent, MessageEvent, StatusEvent
from sqlalchemy.orm import Session as DBSession
from datetime import datetime, timedelta
from pydantic import ValidationError
import hmac, hashlib, os, json
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

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
        event_data = json.loads(body)
        
        webhook_event = WhatsAppWebhookEvent(**event_data)
        
        for message_data in webhook_event.get_message_events():
            message_event = MessageEvent(**message_data)
            
            handler = MessageHandler(db)
            handler.handle(message_event)
            
    except ValidationError as e:
        print(f"Validation error parsing webhook data: {e}")
        raise HTTPException(status_code=400, detail=f"Invalid webhook data: {e}")
    except json.JSONDecodeError as e:
        print(f"JSON decode error: {e}")
        raise HTTPException(status_code=400, detail="Invalid JSON data")
    except Exception as e:
        import traceback
        print(f"Unexpected error processing webhook: {e}")
        print(f"Full traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail="Internal server error")
    
    return {"status": "ok"}

@app.get("/healthz")
def healthz():
    return {"status": "ok"}

