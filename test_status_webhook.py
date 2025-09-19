#!/usr/bin/env python3
"""
Test script to validate our webhook event classes against real WhatsApp status data.
"""

from app.webhooks.models import WhatsAppWebhookEvent, MessageEvent, StatusEvent
from pydantic import ValidationError
import json

# Real WhatsApp status webhook payload from user
status_payload = {
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
                        'statuses': [
                            {
                                'id': 'wamid.HBgLNTY5Nzc2NjQ1NzAVAgARGBIzM0U2NzNERjY4QUM5QjlGMzgA', 
                                'status': 'delivered', 
                                'timestamp': '1756257977', 
                                'recipient_id': '56977664570', 
                                'conversation': {
                                    'id': 'ac8f022f2eeba577617826a16b0318c2', 
                                    'origin': {'type': 'utility'}
                                }, 
                                'pricing': {
                                    'billable': True, 
                                    'pricing_model': 'PMP', 
                                    'category': 'utility', 
                                    'type': 'regular'
                                }
                            }
                        ]
                    }, 
                    'field': 'messages'
                }
            ]
        }
    ]
}

def test_status_webhook_parsing():
    """Test parsing the real status webhook data."""
    try:
        print("Testing status webhook payload parsing...")
        
        # Create WhatsApp webhook event object
        webhook_event = WhatsAppWebhookEvent(**status_payload)
        print("✅ Webhook event created successfully")
        
        # Get messages (should be empty)
        messages = webhook_event.get_messages()
        print(f"✅ Found {len(messages)} messages (expected 0)")
        
        # Get statuses
        statuses = webhook_event.get_statuses()
        print(f"✅ Found {len(statuses)} statuses")
        
        # Get status events
        status_events = webhook_event.get_status_events()
        print(f"✅ Generated {len(status_events)} status events")
        
        # Print the extracted data
        for i, event in enumerate(status_events):
            print(f"\nStatus Event {i + 1}:")
            print(f"  Message ID: {event['message_id']}")
            print(f"  Status: {event['status']}")
            print(f"  Timestamp: {event['timestamp']}")
            print(f"  Recipient ID: {event['recipient_id']}")
            print(f"  Type: {event['type']}")
            
            if 'conversation' in event:
                print(f"  Conversation ID: {event['conversation']['id']}")
                print(f"  Conversation Origin: {event['conversation']['origin']}")
            
            if 'pricing' in event:
                print(f"  Pricing - Billable: {event['pricing']['billable']}")
                print(f"  Pricing - Model: {event['pricing']['pricing_model']}")
                print(f"  Pricing - Category: {event['pricing']['category']}")
            
            # Test creating StatusEvent object
            status_event = StatusEvent(**event)
            print(f"  ✅ StatusEvent object created successfully")
        
        # Test all events
        all_events = webhook_event.get_all_events()
        print(f"✅ All events: {len(all_events)} total")
        
        return True
        
    except ValidationError as e:
        print(f"❌ Validation error: {e}")
        print("Raw error details:")
        for error in e.errors():
            print(f"  - {error}")
        return False
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return False

if __name__ == "__main__":
    success = test_status_webhook_parsing()
    if success:
        print("\n🎉 All status tests passed! The webhook classes handle real status data correctly.")
    else:
        print("\n💥 Status tests failed. Need to fix the webhook classes.")
