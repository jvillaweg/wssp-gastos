import re
from typing import List, Optional, Tuple
from app.database import get_db
from app.models import Category, Expense, Tag, User

class MessageStrategy:
    def __init__(self, db, user: User):
        self.db = db
        self.user = user
    
    def handle_message(self, text: str) -> None:
        # Basic parsing logic; can be extended as needed
        parsed_text = text.strip().lower()
        items = parsed_text.split()
        code = items[0].lower()
        if code == "ct":
            self.create_tag(items[1])
        elif code == "tags":
            return self.list_tags()
        elif code in ("cat", "category", "categoria", "categories", "categorias"):
            return self.list_categories()
        else:
            return self.handle_expense(parsed_text)

    def list_categories(self) -> str:
        categories = self.db.query(Category).all()
        category_names = [f"{category.name} codigo {category.short_name}" for category in categories]
        return "Categorías existentes:\n" + ",\n".join(category_names) if category_names else "No hay categorías existentes."

    def list_tags(self) -> str:
        tags = self.db.query(Tag).all()
        tag_names = [tag.name for tag in tags]
        return "Tags existentes:\n" + ",\n".join(tag_names) if tag_names else "No hay tags existentes."

    def create_tag(self, name: str) -> str:
        existing = self.db.query(Tag).filter_by(name=name).first()
        if existing:
            return f"Tag '{name}' ya existe."
        tag = Tag(name=name)
        self.db.add(tag)
        self.db.commit()
        return f"Tag '{name}' creado."
    
    def handle_expense(self, text: str) -> str:
        parsed_text = text.strip().lower()
        cuerpo: str
        cuerpo, tags = self.split_text_and_tag(parsed_text)
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
            chat_id="not implemented"
        )
        self.db.add(expense)
        if tags:
            for tag in tag_objs:
                expense.tags.append(tag)
        self.db.commit()

        return f"gasto de {currency}{price} en la categoría '{category_obj}' {"con" if tag_objs else "sin"} tags {', '.join(tag.name for tag in tag_objs)} registrado."


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
