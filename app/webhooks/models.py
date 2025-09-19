from typing import List, Optional, Dict, Any, Union
from pydantic import BaseModel, Field
from datetime import datetime
from enum import Enum


class MessageStatusEnum(str, Enum):
    """Possible message status values."""
    SENT = "sent"
    DELIVERED = "delivered"
    READ = "read"
    FAILED = "failed"


class MessageText(BaseModel):
    """Represents the text content of a WhatsApp message."""
    body: str


class ConversationInfo(BaseModel):
    """Represents conversation information from status update."""
    id: str
    origin: Optional[Dict[str, Any]] = None


class PricingInfo(BaseModel):
    """Represents pricing information from status update."""
    billable: bool
    pricing_model: str
    category: str
    type: str


class MessageStatus(BaseModel):
    """Represents a message status update from WhatsApp."""
    id: str  # Message ID that this status refers to
    status: MessageStatusEnum
    timestamp: str
    recipient_id: str
    
    # Optional additional information
    conversation: Optional[ConversationInfo] = None
    pricing: Optional[PricingInfo] = None
    errors: Optional[List[Dict[str, Any]]] = None




class ButtonReply(BaseModel):
    """Represents a button reply in an interactive message."""
    id: str
    title: str
class Interactive(BaseModel):
    """Represents an interactive message element."""
    type: str
    button_reply: Optional[ButtonReply] = None

class WhatsAppMessage(BaseModel):
    """Represents a single WhatsApp message from the webhook."""
    id: str = Field(alias="id")
    from_: str = Field(alias="from")
    timestamp: Optional[str] = None
    type: Optional[str] = None
    text: Optional[MessageText] = None
    interactive: Optional[Interactive] = None

    class Config:
        populate_by_name = True


class MessageValue(BaseModel):
    """Represents the value object containing messages, statuses and metadata."""
    messaging_product: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    contacts: Optional[List[Dict[str, Any]]] = None
    messages: Optional[List[WhatsAppMessage]] = None
    statuses: Optional[List[MessageStatus]] = None


class WebhookChange(BaseModel):
    """Represents a single change in the webhook entry."""
    value: MessageValue
    field: str


class WebhookEntry(BaseModel):
    """Represents a single entry in the webhook event."""
    id: str
    changes: List[WebhookChange]


class WhatsAppWebhookEvent(BaseModel):
    """Main webhook event class for WhatsApp Business API."""
    object: str
    entry: List[WebhookEntry]
    
    def get_messages(self) -> List[WhatsAppMessage]:
        """Extract all messages from the webhook event."""
        messages = []
        for entry in self.entry:
            for change in entry.changes:
                if change.field == "messages" and change.value.messages:
                    messages.extend(change.value.messages)
        return messages
    
    def get_statuses(self) -> List[MessageStatus]:
        """Extract all message statuses from the webhook event."""
        statuses = []
        for entry in self.entry:
            for change in entry.changes:
                if change.field == "messages" and change.value.statuses:
                    statuses.extend(change.value.statuses)
        return statuses
    
    def get_message_events(self) -> List[Dict[str, Any]]:
        """Convert messages to the format expected by MessageHandler."""
        events = []
        for message in self.get_messages():
            event = {
                "from": message.from_,
                "message_id": message.id,
                "text": message.text.body if message.text else "",
                "type": message.type,

            }
            if message.type == "interactive" and message.interactive:
                event["interactive"] = message.interactive
            events.append(event)
        return events
    
    def get_status_events(self) -> List[Dict[str, Any]]:
        """Convert status updates to event format."""
        events = []
        for status in self.get_statuses():
            event = {
                "message_id": status.id,
                "status": status.status.value,
                "timestamp": status.timestamp,
                "recipient_id": status.recipient_id,
                "type": "status"
            }
            if status.errors:
                event["errors"] = status.errors
            if status.conversation:
                event["conversation"] = {
                    "id": status.conversation.id,
                    "origin": status.conversation.origin
                }
            if status.pricing:
                event["pricing"] = {
                    "billable": status.pricing.billable,
                    "pricing_model": status.pricing.pricing_model,
                    "category": status.pricing.category,
                    "type": status.pricing.type
                }
            events.append(event)
        return events
    
    def get_all_events(self) -> List[Dict[str, Any]]:
        """Get both message and status events."""
        return self.get_message_events() + self.get_status_events()


class MessageEvent(BaseModel):
    """Simplified message event for internal processing."""
    from_: str = Field(alias="from")
    message_id: str
    text: str
    timestamp: Optional[datetime] = None
    type: str = "message"
    interactive: Optional[Interactive] = None
    
    class Config:
        populate_by_name = True


class StatusEvent(BaseModel):
    """Status event for message delivery updates."""
    message_id: str
    status: MessageStatusEnum
    timestamp: str
    recipient_id: str
    type: str = "status"
    errors: Optional[List[Dict[str, Any]]] = None
    conversation: Optional[Dict[str, Any]] = None
    pricing: Optional[Dict[str, Any]] = None
