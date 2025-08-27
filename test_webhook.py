#!/usr/bin/env python3
"""
Test script to validate our webhook event classes against real WhatsApp data.
"""

from app.webhook_events import WhatsAppWebhookEvent, MessageEvent, StatusEvent
from pydantic import ValidationError
import json

# Real WhatsApp webhook payload from user
test_payload = {
    'object': 'whatsapp_business_account', 
    'entry': [
        {
            'id': '24194856996851199', 
            'changes': [
                {
                    'value': {
                        'messaging_product': 'whatsapp', 
                        'metadata': {
                            'display_phone_number': '56935737510', 
                            'phone_number_id': '803124869540483'
                        }, 
                        'contacts': [
                            {
                                'profile': {'name': 'Jvillaweg'}, 
                                'wa_id': '56977664570'
                            }
                        ], 
                        'messages': [
                            {
                                'from': '56977664570', 
                                'id': 'wamid.HBgLNTY5Nzc2NjQ1NzAVAgASGBQzQTEwNjdERDg1QkU3RENEQTlFNwA=', 
                                'timestamp': '1756163234', 
                                'text': {'body': 'A'}, 
                                'type': 'text'
                            }
                        ]
                    }, 
                    'field': 'messages'
                }
            ]
        }
    ]
}

def test_webhook_parsing():
    """Test parsing the real webhook data."""
    try:
        print("Testing webhook payload parsing...")
        
        # Create WhatsApp webhook event object
        webhook_event = WhatsAppWebhookEvent(**test_payload)
        print("✅ Webhook event created successfully")
        
        # Get messages
        messages = webhook_event.get_messages()
        print(f"✅ Found {len(messages)} messages")
        
        # Get message events
        message_events = webhook_event.get_message_events()
        print(f"✅ Generated {len(message_events)} message events")
        
        # Print the extracted data
        for i, event in enumerate(message_events):
            print(f"\nMessage Event {i + 1}:")
            print(f"  From: {event['from']}")
            print(f"  Message ID: {event['message_id']}")
            print(f"  Text: {event['text']}")
            print(f"  Type: {event['type']}")
            
            # Test creating MessageEvent object
            message_event = MessageEvent(**event)
            print(f"  ✅ MessageEvent object created successfully")
        
        # Test status events (should be empty for this payload)
        status_events = webhook_event.get_status_events()
        print(f"✅ Status events: {len(status_events)} (expected 0 for message payload)")
        
        return True
        
    except ValidationError as e:
        print(f"❌ Validation error: {e}")
        return False
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return False

if __name__ == "__main__":
    success = test_webhook_parsing()
    if success:
        print("\n🎉 All tests passed! The webhook classes handle the real data correctly.")
    else:
        print("\n💥 Tests failed. Need to fix the webhook classes.")
