import re
from typing import List, Optional, Tuple
from app.database import get_db
from app.models import Category, Expense, Tag, User
from app.wa_sender import WhatsAppSender
from app.webhook_events import Interactive
import datetime


class MessageStrategy:
    def __init__(self, db, user: User):
        self.db = db
        self.user = user

    def handle_interactive(self, interactive: Interactive) -> None:
        # Handle interactive messages
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
                WhatsAppSender.send_message(
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

                # Beautiful rejection message
                message = f"❌ *Gasto rechazado:*\n{expense}\n\nEl gasto ha sido rechazado y no se guardará en tus registros."
            else:
                message = f"⚠️ Acción no reconocida: {instruction}"

            WhatsAppSender.send_message(self.user.phone, message)

    def handle_message(self, text: str) -> None:
        # Basic parsing logic; can be extended as needed
        parsed_text = text.strip().lower()
        items = parsed_text.split()
        code = items[0].lower()
        response = None
        if code == "ct":
            response = self.create_tag(items[1])
        elif code in ("tags", "etiquetas"):
            response = self.list_tags()
        elif code in ("cat", "category", "categoria", "categories", "categorias"):
            response = self.list_categories()
        else:
            self.handle_expense(parsed_text)
        if response:
            WhatsAppSender.send_message(self.user.phone, response)

    def list_categories(self) -> str:
        categories = self.db.query(Category).all()
        category_names = [
            f"{category.name} codigo {category.short_name}" for category in categories
        ]
        return (
            "Categorías existentes:\n" + ",\n".join(category_names)
            if category_names
            else "No hay categorías existentes."
        )

    def list_tags(self) -> str:
        tags = self.db.query(Tag).all()
        tag_names = [tag.name for tag in tags]
        return (
            "Etiquetas existentes:\n" + ",\n".join(tag_names)
            if tag_names
            else "No hay etiquetas existentes."
        )

    def create_tag(self, name: str) -> str:
        existing = self.db.query(Tag).filter_by(name=name).first()
        if existing:
            return f"Etiqueta '{name}' ya existe."
        tag = Tag(name=name)
        self.db.add(tag)
        self.db.commit()
        return f"Etiqueta '{name}' creada."

    def handle_expense(self, text: str) -> None:
        parsed_text = text.strip().lower()
        cuerpo: str
        cuerpo, tags = self.split_text_and_tag(parsed_text)
        cuerpo, date_str = self.extract_date(cuerpo)
        tag_objs = []
        if tags:
            for tag in tags:
                tag_obj = self.db.query(Tag).filter_by(name=tag).first()
                if not tag_obj:
                    tag_obj = Tag(name=tag)
                    self.db.add(tag_obj)
                tag_objs.append(tag_obj)
            self.db.commit()

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

        category_obj = self.db.query(Category).filter_by(short_name=category).first()

        expense = Expense(
            user_id=self.user.id,
            amount=price,
            category=category_obj,
            description=description,
            currency=currency,
            raw_text=text,
            chat_id=self.user.phone,
            expense_date=date_str if date_str else datetime.date.today().isoformat(),
        )
        self.db.add(expense)
        if tags:
            for tag in tag_objs:
                expense.tags.append(tag)
        self.db.commit()
        text = f"💰 *Gasto en proceso:* \n{expense}"
        WhatsAppSender.send_interactive_message(self.user.phone, text, expense.id)

    def split_text_and_tag(self, texto: str) -> Tuple[str, Optional[List[str]]]:
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
    
    def extract_date(self, text: str) -> Tuple[str, Optional[str]]:
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
    


