from datetime import datetime, timezone
from typing import Optional
from app.core.user_manager import UserManager
from app.core.expense_manager import ExpenseManager
from app.core.tag_manager import TagManager
from app.services.rate_limiter import RateLimiter
from app.services.whatsapp_service import WhatsAppService
from app.models import MessageLog
from app.webhooks.models import MessageEvent


class MessageHandler:
    """Main handler for processing incoming WhatsApp messages."""
    
    def __init__(self, db):
        self.db = db
        self.rate_limiter = RateLimiter()
        self.user_manager = UserManager(db)

    def handle(self, event: MessageEvent, raw_payload: dict = None):
        """Process an incoming message event with atomic transaction handling."""
        phone_number = event.from_
        message_id = event.message_id
        text: str = event.text
        
        # Check for duplicate messages
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
            chat_id=phone_number,
            direction="in",
            text=text,
            payload_json=raw_payload,
            status="received"
        )
        self.db.add(message_log)
        self.db.commit()
        
        try:
            # Start transaction for message processing
            self.db.begin()
            
            # Get or create user
            user = self.user_manager.get_or_create_user(phone_number)
            
            # Rate limiting check
            if not self.rate_limiter.check(user.id):
                WhatsAppService.send_message(phone_number, "Demasiados mensajes. Espera un momento.")
                message_log.status = "rate_limited"
                self.db.commit()
                return
                
            # Blocked user check
            if self.user_manager.is_user_blocked(user):
                WhatsAppService.send_message(phone_number, "Tu acceso está bloqueado. Contacta soporte.")
                message_log.status = "blocked"
                self.db.commit()
                return
                
            # Update last_seen_at
            user.last_seen_at = datetime.now(timezone.utc)

            # Process the message
            if event.type == "interactive" and event.interactive:
                expense_manager = ExpenseManager(self.db, user)
                expense_manager.handle_interactive_response(event.interactive)
            else:
                response = self._handle_text_message(text, user)
                if response:  # Only send if there's a response
                    WhatsAppService.send_message(phone_number, response)

            # Mark message as successfully processed
            message_log.status = "processed"
            
            # Commit all changes atomically
            self.db.commit()
            
        except Exception as e:
            # Rollback all changes if anything fails
            self.db.rollback()
            
            # Mark message as failed in a separate transaction
            try:
                message_log.status = "failed"
                message_log.error = str(e)
                self.db.commit()
            except Exception as log_error:
                print(f"Failed to log error: {log_error}")
                
            WhatsAppService.send_message(phone_number, "Ocurrió un error procesando tu mensaje. Intenta nuevamente.")
            raise

    def _handle_text_message(self, text: str, user) -> Optional[str]:
        """Route text messages to appropriate handlers."""
        parsed_text = text.strip().lower()  
        items = parsed_text.split()
        code = items[0].lower()
        
        if code == "ct":
            tag_manager = TagManager(self.db)
            return tag_manager.create_tag(items[1])
        elif code in ("tags", "etiquetas"):
            tag_manager = TagManager(self.db)
            return tag_manager.list_tags()
        elif code in ("cat", "category", "categoria", "categories", "categorias"):
            expense_manager = ExpenseManager(self.db, user)
            return expense_manager.list_categories()
        elif code in ("tutorial", "ayuda", "help"):
            return self._get_tutorial_text()
        elif code == "gastos":
            expense_manager = ExpenseManager(self.db, user)
            return expense_manager.list_expenses(parsed_text)
        else:
            # Handle expense creation
            expense_manager = ExpenseManager(self.db, user)
            expense_manager.create_expense_from_text(parsed_text)
            return None  # Expense handling sends its own messages
    
    def _get_tutorial_text(self) -> str:
        """Return tutorial text explaining how to use the app."""
        return """📚 *¡Bienvenido al Bot de Gastos!*

🎯 *Cómo registrar un gasto:*
Envía: `[monto] [categoría] [descripción] [fecha] [@etiquetas]`

📝 *Ejemplos:*
• `15000 comida almuerzo` - Gasto básico
• `25000 transporte uber 15/03` - Con fecha
• `8500 comida café @trabajo` - Con etiqueta
• `12.50 comida sandwich` - En USD (con decimales)

📅 *Formatos de fecha:*
• `15/03` o `15-03` (día/mes del año actual)
• `15/03/2024` o `15-03-2024` (fecha completa)

🏷️ *Etiquetas:*
• Agregar: `@trabajo @personal @urgente`
• Crear nueva: `ct nombreetiqueta`
• Ver todas: `tags` o `etiquetas`

📂 *Categorías:*
• Ver todas: `cat` o `categorias`
• Usar código corto o nombre en el gasto

✅ *Confirmación:*
Después de enviar un gasto, recibirás botones para *Confirmar* o *Rechazar*.

💡 *Tips:*
• Si no especificas categoría, usa `x`
• Las fechas sin año asumen el año actual
• Los montos con decimales se consideran USD

¡Empieza a registrar tus gastos ahora! 💸"""
