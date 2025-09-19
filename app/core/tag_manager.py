from typing import List
from app.models import Tag


class TagManager:
    """Handles tag-related operations."""
    
    def __init__(self, db):
        self.db = db
    
    def list_tags(self) -> str:
        """List all available tags."""
        tags = self.db.query(Tag).all()
        tag_names = [tag.name for tag in tags]
        return (
            "Etiquetas existentes:\n" + ",\n".join(tag_names)
            if tag_names
            else "No hay etiquetas existentes."
        )
    
    def create_tag(self, name: str) -> str:
        """Create a new tag."""
        existing = self.db.query(Tag).filter_by(name=name).first()
        if existing:
            return f"Etiqueta '{name}' ya existe."
        tag = Tag(name=name)
        self.db.add(tag)
        self.db.commit()
        return f"Etiqueta '{name}' creada."
    
    def get_or_create_tags(self, tag_names: List[str]) -> List[Tag]:
        """Get existing tags or create new ones."""
        tag_objs = []
        for tag_name in tag_names:
            tag_obj = self.db.query(Tag).filter_by(name=tag_name).first()
            if not tag_obj:
                tag_obj = Tag(name=tag_name)
                self.db.add(tag_obj)
            tag_objs.append(tag_obj)
        self.db.commit()
        return tag_objs
