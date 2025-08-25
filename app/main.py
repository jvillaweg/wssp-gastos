from fastapi import FastAPI, Request, HTTPException, Depends
from fastapi.responses import PlainTextResponse
from app.models import User, Consent, Session, UserRole, RoleEnum
from app.database import get_db
from app.message_handler import MessageHandler
from sqlalchemy.orm import Session as DBSession
from datetime import datetime, timedelta
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
    print(request)
    if not verify_signature(request, body):
        raise HTTPException(status_code=403, detail="Invalid signature")
    
    event_data = json.loads(body)
    print(event_data)

    # Parse WhatsApp webhook format
    if "entry" in event_data:
        for entry in event_data["entry"]:
            if "changes" in entry:
                for change in entry["changes"]:
                    if change.get("field") == "messages":
                        value = change.get("value", {})
                        if "messages" in value:
                            for message in value["messages"]:
                                # Extract message data
                                event = {
                                    "from": message.get("from"),
                                    "message_id": message.get("id"),
                                    "text": message.get("text", {}).get("body", "")
                                }
                                # Handle message
                                handler = MessageHandler(db)
                                handler.handle(event)
    
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
