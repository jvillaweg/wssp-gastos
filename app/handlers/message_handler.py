from datetime import datetime, timezone
from typing import Optional
from app.core.user_manager import UserManager
from app.core.expense_manager import ExpenseManager
from app.core.category_manager import CategoryManager
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
        stripped_text = text.strip()
        if not stripped_text:
            return "❌ El mensaje está vacío."

        parsed_text = stripped_text.lower()
        items = parsed_text.split()
        if not items:
            return "❌ El mensaje está vacío."
        code = items[0]

        if code in ("cat", "category", "categoria", "categories", "categorias"):
            category_manager = CategoryManager(self.db, user)
            original_first_word = stripped_text.split()[0]
            remainder = stripped_text[len(original_first_word):].strip()
            return category_manager.handle(remainder)
        elif code in ("tag", "tags", "etiqueta", "etiquetas"):
            tag_manager = TagManager(self.db, user)
            if len(items) > 1:
                action = items[1].lower()
                tag_name = items[2] if len(items) > 2 else None
                return tag_manager.action(action, tag_name)
            else:
                return tag_manager.list_tags()
        elif code in ("tutorial", "ayuda", "help"):
            return self._get_tutorial_text()
        elif code in ("gastos", "g"):
            expense_manager = ExpenseManager(self.db, user)
            return expense_manager.list_expenses(parsed_text)
        elif code in ("resumen", "summary", "total"):
            expense_manager = ExpenseManager(self.db, user)
            return expense_manager.get_summary(parsed_text)
        elif code in ("borrar", "delete", "eliminar", "undo", "d"):
            expense_manager = ExpenseManager(self.db, user)
            return expense_manager.delete_last_expense()
        elif code in ("buscar", "search", "encontrar", "find", "f"):
            expense_manager = ExpenseManager(self.db, user)
            search_term = " ".join(items[1:]) if len(items) > 1 else ""
            return expense_manager.search_expenses(search_term)
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
• Agregar al gasto: `@trabajo @personal @urgente`

📂 *Categorías:*
• Ver todas: `cat`, `categoria`, `categories` o `categorias`
• Gestionar: `cat help`, `cat c <nombre>`, `cat u <id>`, `cat d <id>`

📊 *Ver gastos:*
• Todos: `gastos` o `g`
• Por mes: `gastos enero` o `gastos 3`
• Con etiquetas: `gastos @trabajo`
• Con opciones: `gastos cat tags` (mostrar categorías y etiquetas)

📈 *Resúmenes:*
• Hoy: `resumen` o `resumen hoy`
• Semanal: `resumen semana`
• Mensual: `resumen mes` (mes actual)
• Mes específico: `resumen mes enero` o `resumen mes 3`

🔍 *Buscar gastos:*
• Por descripción: `buscar almuerzo`
• Por categoría: `buscar comida`
• Por monto: `buscar 5000`

🗑️ *Eliminar último gasto:*
• `borrar`, `delete`, `eliminar` o `undo`

🏷️ *Gestión de etiquetas:*
• Ver etiquetas: `tags` o `etiquetas`
• Crear etiqueta: `tags create nombre`
• Eliminar etiqueta: `tags delete nombre`

💬 *Comandos principales:*
• `tutorial` / `ayuda` / `help` - Esta ayuda
• `cat` - Ver categorías
• `gastos` / `g` - Listar gastos
• `resumen` - Resumen diario
• `resumen mes [mes]` - Resumen mensual
• `buscar [término]` - Buscar gastos
• `borrar` - Eliminar último gasto
• `tags` - Ver/gestionar etiquetas

✅ *Confirmación de gastos:*
Después de enviar un gasto, recibirás botones para *Confirmar* o *Rechazar*.

💡 *Tips útiles:*
• Si no especificas categoría, usa `x`
• Las fechas sin año asumen el año actual
• Los montos con decimales se consideran USD
• Puedes usar múltiples etiquetas: `@trabajo @urgente`
• Los resúmenes muestran totales y estadísticas detalladas
• La búsqueda funciona en descripciones, categorías y montos

🚀 ¡Empieza a registrar tus gastos ahora! 💸"""
