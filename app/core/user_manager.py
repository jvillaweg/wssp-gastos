from app.models import User


class UserManager:
    """Handles user-related operations."""
    
    def __init__(self, db):
        self.db = db
    
    def get_or_create_user(self, phone_number: str) -> User:
        """Get existing user or create a new one."""
        user = self.db.query(User).filter_by(phone=phone_number).first()
        if not user:
            user = User(phone=phone_number)
            self.db.add(user)
            self.db.commit()
        return user
    
    def is_user_blocked(self, user: User) -> bool:
        """Check if user is blocked."""
        return user.is_blocked
