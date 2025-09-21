from typing import List
from app.models import Tag, User


class TagManager:
    """Handles tag-related operations."""
    
    def __init__(self, db, user: User):
        self.db = db
        self.user = user

    def action(self, action: str, tag_name: str = None) -> str:
        """Perform actions like creating or listing tags."""
        if action == "list":
            return self.list_tags()
        else:
            return "Acción no reconocida. Usa 'create <tag_name>' o 'list'."
    
    def list_tags(self) -> str:
        """List all tags used by a user."""
        tags = self.db.query(Tag).join(Tag.expenses).filter_by(user_id=self.user.id).distinct().all()
        if not tags:
            return "No hay etiquetas disponibles."
        
        tag_names = [tag.name for tag in tags]
        return "Etiquetas existentes:\n" + ", ".join(tag_names)
    
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
