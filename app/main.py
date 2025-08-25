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
async def verify_webhook(hub_mode: str | None = None,
                         hub_verify_token: str | None = None,
                         hub_challenge: str | None = None,
                         mode: str | None = None,
                         token: str | None = None,
                         challenge: str | None = None):
    # Aceptar ambas variantes por si algún proxy renombra las keys
    mode = hub_mode or mode or ""
    verify_token = hub_verify_token or token or ""
    challenge_val = hub_challenge or challenge or ""

    # Debug logging (remove in production)
    print(f"Received: mode='{mode}', verify_token='{verify_token}', challenge='{challenge_val}'")
    print(f"Expected token: '{VERIFY_TOKEN}'")
    print(f"Token match: {verify_token == VERIFY_TOKEN}")

    if mode == "subscribe" and verify_token == VERIFY_TOKEN and challenge_val:
        # Debe ser texto plano, sin comillas
        return PlainTextResponse(content=challenge_val, status_code=200)
    
    raise HTTPException(status_code=403, detail=f"Verification failed. Mode: {mode}, Token provided: {verify_token != ''}")
    raise HTTPException(status_code=403, detail="Verification failed")

@app.post("/webhook/meta")
async def webhook_event(request: Request, db: DBSession = Depends(get_db)):
    body = await request.body()
    if not verify_signature(request, body):
        raise HTTPException(status_code=403, detail="Invalid signature")
    
    event_data = json.loads(body)
    
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
