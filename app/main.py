from fastapi import FastAPI, Request, HTTPException, Depends
from fastapi.responses import PlainTextResponse
from app.database import get_db
from app.handlers.webhook_handler import WebhookHandler
from sqlalchemy.orm import Session as DBSession
from datetime import datetime
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
        webhook_handler = WebhookHandler(db)
        return webhook_handler.process_webhook(event_data)
        
    except json.JSONDecodeError as e:
        print(f"JSON decode error: {e}")
        raise HTTPException(status_code=400, detail="Invalid JSON data")

@app.get("/healthz")
def healthz():
    return {"status": "ok"}

@app.get("/ping")
def ping():
    """Lightweight ping endpoint for warming up Lambda"""
    return {"status": "warm", "timestamp": datetime.now().isoformat()}

