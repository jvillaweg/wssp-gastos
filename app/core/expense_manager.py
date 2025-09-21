import re
import datetime
from typing import List, Optional, Tuple
from app.models import Category, Expense, Tag, User
from app.core.tag_manager import TagManager
from app.services.whatsapp_service import WhatsAppService
from app.webhooks.models import Interactive


class ExpenseManager:
    """Handles expense-related operations and business logic."""
    
    def __init__(self, db, user: User):
        self.db = db
        self.user = user
        self.tag_manager = TagManager(db)
    
    def list_categories(self) -> str:
        """List all available categories."""
        categories = self.db.query(Category).all()
        category_names = [
            f"{category.name} codigo {category.short_name}" for category in categories
        ]
        return (
            "Categorías existentes:\n" + ",\n".join(category_names)
            if category_names
            else "No hay categorías existentes."
        )
    
    def handle_interactive_response(self, interactive: Interactive) -> None:
        """Handle interactive button responses for expense confirmation/rejection."""
        if interactive.type == "button_reply" and interactive.button_reply:
            button_id: str = interactive.button_reply.id
            instruction, id_str = button_id.split("_", 1)
            expense_id = int(id_str)
            expense: Expense = (
                self.db.query(Expense)
                .filter_by(id=expense_id, user_id=self.user.id)
                .first()
            )

            if not expense:
                WhatsAppService.send_message(
                    self.user.phone, "❌ No se encontró el gasto solicitado."
                )
                return

            if instruction == "confirm":
                expense.status = "confirmed"
                self.db.commit()
                message = f"✅ *¡Gasto confirmado exitosamente!*\n{expense}\n\n¡Tu gasto ha sido registrado correctamente! 💫"

            elif instruction == "decline":
                expense.status = "rejected"
                self.db.commit()
                message = f"❌ *Gasto rechazado:*\n{expense}\n\nEl gasto ha sido rechazado y no se guardará en tus registros."
            else:
                message = f"⚠️ Acción no reconocida: {instruction}"

            WhatsAppService.send_message(self.user.phone, message)
    
    def create_expense_from_text(self, text: str) -> None:
        """Process expense creation from text message."""
        parsed_text = text.strip().lower()
        cuerpo: str
        cuerpo, tags = self._split_text_and_tag(parsed_text)
        cuerpo, date_str = self._extract_date(cuerpo)
        
        # Handle tags
        tag_objs = []
        if tags:
            tag_objs = self.tag_manager.get_or_create_tags(tags)

        # Parse expense details
        items = cuerpo.split()
        price = items[0]
        currency = "CLP"
        
        if ("," in price) or ("." in price):
            price = price.replace(",", ".")
            price = float(price + "0")
            currency = "USD"
        else:
            price = int(price)
            
        category = items[1] if len(items) > 1 else "x"
        description = " ".join(items[2:]) if len(items) > 2 else "No description"

        category_obj = self.db.query(Category).filter(
            (Category.short_name.ilike(category)) | (Category.name.ilike(category))
        ).first()

        # Create expense
        expense = Expense(
            user_id=self.user.id,
            amount=price,
            category=category_obj,
            description=description,
            currency=currency,
            raw_text=text,
            chat_id=self.user.phone,
            expense_date=date_str,
        )
        self.db.add(expense)
        
        # Add tags
        if tags:
            for tag in tag_objs:
                expense.tags.append(tag)
        self.db.commit()
        
        # Send confirmation message with buttons
        confirmation_text = f"💰 *Gasto en proceso:* \n{expense}"
        WhatsAppService.send_confirm_interaction(self.user.phone, confirmation_text, expense.id)
    
    def _split_text_and_tag(self, texto: str) -> Tuple[str, Optional[List[str]]]:
        """
        Separa el texto de una o más etiquetas con @ al final.
        Retorna (texto_sin_tags, tags) como tupla.
        Si no hay etiquetas, tags será None.
        """
        # Busca todas las etiquetas @tag al final del texto
        tags = re.findall(r"@([^\s]+)", texto)
        # Elimina las etiquetas del texto
        cuerpo = re.sub(r"\s*@([^\s]+)", "", texto).strip()
        return cuerpo, tags if tags else None
    
    def _extract_date(self, text: str) -> Tuple[str, Optional[str]]:
        """
        Extracts a date from the text in formats:
        dd/mm/yyyy, dd-mm-yyyy, dd/mm/yy, dd-mm-yy, dd/mm, dd-mm
        If only day and month, assumes current year.
        Returns a tuple (text_without_date, date_in_YYYY-MM-DD format or None).
        """
        date_patterns = [
            r"(\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b)",  # dd/mm/yyyy or dd-mm-yyyy or dd/mm/yy or dd-mm-yy
            r"(\b\d{1,2}[/-]\d{1,2}\b)",              # dd/mm or dd-mm
        ]
        for pattern in date_patterns:
            match = re.search(pattern, text)
            if match:
                date_str = match.group(1)
                try:
                    if re.match(r"\d{1,2}[/-]\d{1,2}[/-]\d{2,4}", date_str):
                        # Handle full date with year
                        parts = re.split(r"[/-]", date_str)
                        day = int(parts[0])
                        month = int(parts[1])
                        year = int(parts[2])
                        if year < 100:  # Handle two-digit year
                            year += 2000
                    elif re.match(r"\d{1,2}[/-]\d{1,2}", date_str):
                        # Handle date without year, assume current year
                        parts = re.split(r"[/-]", date_str)
                        day = int(parts[0])
                        month = int(parts[1])
                        year = datetime.datetime.now().year
                    else:
                        continue
                    
                    extracted_date = datetime.datetime(year, month, day, 12, 0)
                    text_without_date = text.replace(date_str, "").strip()
                    return text_without_date, extracted_date.isoformat()
                except ValueError:
                    continue
        return text, datetime.datetime.now().isoformat()

    def list_expenses(self, text: str) -> str:
        """List expenses for the user based on the provided text."""
        user = self.user
        text = text.strip().lower()
        text, tags = self._split_text_and_tag(text)

        if tags:
            expenses_query = self.db.query(Expense).filter(Expense.user_id == user.id)
            expenses_query = expenses_query.join(Expense.tags).filter(Tag.name.in_(tags))
            expenses = expenses_query.order_by(Expense.expense_date.desc()).all()
            if not expenses:
                return "No se encontraron gastos con las etiquetas especificadas."
            total_clp = self.parse_money_text(sum(exp.amount for exp in expenses if exp.currency == "CLP"), "CLP")
            total_usd = self.parse_money_text(sum(exp.amount for exp in expenses if exp.currency == "USD"), "USD")
            text_response = f"📋 *Gastos con etiquetas {', '.join(tags)}:* {total_clp} CLP / {total_usd} USD\n\n"
            exp: Expense
            for exp in expenses:
                text_response += exp.custom_str(cat=False, tags=True) + "\n\n"
            return text_response
        items = text.split()
        month = items[1] if len(items) > 1 else None
        cat = True if "cat" in items else False
        tags = True if "tags" in items else False
        # month can either be numero 1-12 or nombre del mes en español
        meses = {
            "enero": 1, "febrero": 2, "marzo": 3, "abril": 4,
            "mayo": 5, "junio": 6, "julio": 7, "agosto": 8,
            "septiembre": 9, "octubre": 10, "noviembre": 11, "diciembre": 12
        }
        if month:
            try:
                month = int(month)
                if month < 1 or month > 12:
                    raise ValueError
            except ValueError:
                month = meses.get(month.lower())
                if not month:
                    return "❌ Mes no válido. Usa número (1-12) o nombre del mes en español."
        expenses_query = self.db.query(Expense).filter(Expense.user_id == user.id)
        if month:
            current_year = datetime.datetime.now().year
            start_date = datetime.datetime(current_year, month, 1)
            if month == 12:
                end_date = datetime.datetime(current_year + 1, 1, 1)
            else:
                end_date = datetime.datetime(current_year, month + 1, 1)
            expenses_query = expenses_query.filter(
                Expense.expense_date >= start_date,
                Expense.expense_date < end_date
            )
        expenses = expenses_query.order_by(Expense.expense_date.desc()).all()
        if not expenses:
            return "No se encontraron gastos para el período especificado."
        total_clp = self.parse_money_text(sum(exp.amount for exp in expenses if exp.currency == "CLP"), "CLP")
        total_usd = self.parse_money_text(sum(exp.amount for exp in expenses if exp.currency == "USD"), "USD")
        # Get month name in Spanish

        month_str = [k for k, v in meses.items() if v == month]
        text_response = f"📋 *Gastos {month_str[0]}:* {total_clp} CLP / {total_usd} USD\n\n"
        exp: Expense
        for exp in expenses:
            text_response += exp.custom_str(cat, tags) + "\n\n"
        return text_response

    def parse_money_text(self, number: float, currency: str) -> str:
        """Parse and return a human-readable monetary $1,200.50 for usd or $1.200 for clp"""
        if currency == "USD":
            return f"${number:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        elif currency == "CLP":
            return f"${int(number):,}".replace(",", ".")
        else:
            return f"{number} {currency}"