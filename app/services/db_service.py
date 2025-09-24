from typing import List
from sqlalchemy.orm import Session,Query
from app.models import Expense


class DB:
    def __init__(self, db: Session):
        self.session = db

    def get_expenses(self, user_id: int) -> Query[Expense]:
        return self.session.query(Expense).filter(Expense.user_id == user_id, Expense.status == "confirmed")