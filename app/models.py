# app/models.py
from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import AsyncAttrs
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


# ---------- Base ----------

class Base(AsyncAttrs, DeclarativeBase):
    """Base declarativa (SQLAlchemy 2.x, async)."""
    pass


# ---------- Mixins ----------

class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


# ---------- User & Channels ----------

class User(Base, TimestampMixin):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column("user_id", BigInteger, primary_key=True)
    phone: Mapped[str] = mapped_column(String(16), unique=True, nullable=False)
    full_name: Mapped[Optional[str]] = mapped_column(String(120))
    email: Mapped[Optional[str]] = mapped_column(String(160), index=True)
    status: Mapped[str] = mapped_column(String(16), default="active", nullable=False)
    is_blocked: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    last_seen_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    channels: Mapped[list[UserChannel]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    settings: Mapped[Optional[UserSettings]] = relationship(
        back_populates="user", uselist=False, cascade="all, delete-orphan"
    )
    payment_methods: Mapped[list[PaymentMethod]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    expenses: Mapped[list[Expense]] = relationship(
        foreign_keys="Expense.user_id", back_populates="user", cascade="all, delete-orphan"
    )
    budgets: Mapped[list[Budget]] = relationship(
        foreign_keys="Budget.user_id", back_populates="user", cascade="all, delete-orphan"
    )
    rules: Mapped[list[UserRule]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    group_memberships: Mapped[list[GroupMember]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )


class UserChannel(Base, TimestampMixin):
    __tablename__ = "user_channel"
    __table_args__ = (
        UniqueConstraint("provider", "chat_id", name="uq_channel_provider_chat"),
        Index("ix_user_channel_user_id", "user_id"),
    )

    id: Mapped[int] = mapped_column("user_channel_id", BigInteger, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.user_id", ondelete="CASCADE"), index=True
    )
    provider: Mapped[str] = mapped_column(String(16), nullable=False)  # 'meta' | 'twilio'
    chat_id: Mapped[str] = mapped_column(String(64), nullable=False)   # wa_id / E164
    is_primary: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    user: Mapped[User] = relationship(back_populates="channels")


class UserSettings(Base, TimestampMixin):
    __tablename__ = "user_settings"

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.user_id", ondelete="CASCADE"), primary_key=True
    )
    default_currency: Mapped[str] = mapped_column(String(8), default="CLP", nullable=False)
    timezone: Mapped[str] = mapped_column(String(64), default="America/Santiago", nullable=False)
    locale: Mapped[str] = mapped_column(String(16), default="es-CL", nullable=False)
    confirm_before_save: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    user: Mapped[User] = relationship(back_populates="settings")


# ---------- GROUP / HOUSEHOLD ----------

class Group(Base, TimestampMixin):
    __tablename__ = "group_account"
    __table_args__ = (UniqueConstraint("name", name="uq_group_name"),)

    id: Mapped[int] = mapped_column("group_id", BigInteger, primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    owner_user_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.user_id", ondelete="SET NULL")
    )

    owner: Mapped[Optional[User]] = relationship(foreign_keys=[owner_user_id])
    members: Mapped[list[GroupMember]] = relationship(
        back_populates="group", cascade="all, delete-orphan"
    )
    settings: Mapped[Optional[GroupSettings]] = relationship(
        back_populates="group", uselist=False, cascade="all, delete-orphan"
    )

    expenses: Mapped[list[Expense]] = relationship(
        back_populates="group", cascade="all, delete-orphan"
    )
    budgets: Mapped[list[Budget]] = relationship(
        back_populates="group", cascade="all, delete-orphan"
    )


class GroupMember(Base, TimestampMixin):
    __tablename__ = "group_member"
    __table_args__ = (
        UniqueConstraint("group_id", "user_id", name="uq_group_member"),
        Index("ix_group_member_group_id", "group_id"),
        Index("ix_group_member_user_id", "user_id"),
    )

    id: Mapped[int] = mapped_column("group_member_id", BigInteger, primary_key=True)
    group_id: Mapped[int] = mapped_column(
        ForeignKey("group_account.group_id", ondelete="CASCADE")
    )
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.user_id", ondelete="CASCADE")
    )
    role: Mapped[str] = mapped_column(String(16), default="member", nullable=False)  # owner|admin|member
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    group: Mapped[Group] = relationship(back_populates="members")
    user: Mapped[User] = relationship(back_populates="group_memberships")


class GroupSettings(Base, TimestampMixin):
    __tablename__ = "group_settings"

    group_id: Mapped[int] = mapped_column(
        ForeignKey("group_account.group_id", ondelete="CASCADE"), primary_key=True
    )
    default_currency: Mapped[str] = mapped_column(String(8), default="CLP", nullable=False)
    timezone: Mapped[str] = mapped_column(String(64), default="America/Santiago", nullable=False)
    locale: Mapped[str] = mapped_column(String(16), default="es-CL", nullable=False)
    confirm_before_save: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    group: Mapped[Group] = relationship(back_populates="settings")


# ---------- Categories (hierarchical) ----------

class Category(Base, TimestampMixin):
    __tablename__ = "categories"
    __table_args__ = (
        UniqueConstraint("name", "parent_id", name="uq_category_name_parent"),
        Index("ix_categories_parent_id", "parent_id"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    parent_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("categories.id", ondelete="SET NULL")
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    is_system: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    emoji: Mapped[Optional[str]] = mapped_column(String(8))
    short_name: Mapped[Optional[str]] = mapped_column(String(48))

    parent: Mapped[Optional[Category]] = relationship(
        remote_side="Category.id", back_populates="children"
    )
    children: Mapped[list[Category]] = relationship(
        back_populates="parent", cascade="all, delete-orphan", foreign_keys=[parent_id]
    )

    expenses: Mapped[list[Expense]] = relationship(back_populates="category")

    def __str__(self):
        parent_name = f"{self.parent.name} > " if self.parent else ""
        return f"{parent_name}{self.name}"

# ---------- Merchant & Payment ----------

class Merchant(Base, TimestampMixin):
    __tablename__ = "merchants"
    __table_args__ = (Index("ix_merchants_normalized_name", "normalized_name"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    normalized_name: Mapped[str] = mapped_column(String(120), nullable=False)
    default_category_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("categories.id", ondelete="SET NULL")
    )

    default_category: Mapped[Optional[Category]] = relationship()
    expenses: Mapped[list[Expense]] = relationship(back_populates="merchant")


class PaymentMethod(Base, TimestampMixin):
    __tablename__ = "payment_methods"
    __table_args__ = (Index("ix_payment_methods_user_id", "user_id"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(60), nullable=False)  # cash, visa, amex, bank
    last4: Mapped[Optional[str]] = mapped_column(String(4))

    user: Mapped[User] = relationship(back_populates="payment_methods")
    expenses: Mapped[list[Expense]] = relationship(back_populates="payment_method")


# ---------- Expense, Tagging, Budgets ----------

class Expense(Base, TimestampMixin):
    __tablename__ = "expenses"
    __table_args__ = (
        Index("ix_expenses_user_id", "user_id"),
        Index("ix_expenses_group_id", "group_id"),
        Index("ix_expenses_expense_date", "expense_date"),
        CheckConstraint(
            "(user_id IS NOT NULL) OR (group_id IS NOT NULL)",
            name="ck_expense_owner_scope",
        ),  # al menos un dueño (usuario o grupo)
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)

    # Scope: usuario, grupo, o ambos
    user_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.user_id", ondelete="CASCADE")
    )
    group_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("group_account.group_id", ondelete="CASCADE")
    )

    # Auditoría del creador
    created_by_user_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.user_id", ondelete="SET NULL")
    )

    amount: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(8), default="CLP", nullable=False)

    category_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("categories.id", ondelete="SET NULL")
    )
    category: Mapped[Optional[Category]] = relationship(back_populates="expenses")

    description: Mapped[Optional[str]] = mapped_column(Text)
    merchant_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("merchants.id", ondelete="SET NULL")
    )
    merchant: Mapped[Optional[Merchant]] = relationship(back_populates="expenses")

    payment_method_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("payment_methods.id", ondelete="SET NULL")
    )
    payment_method: Mapped[Optional[PaymentMethod]] = relationship(
        back_populates="expenses"
    )

    expense_date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    source: Mapped[str] = mapped_column(String(24), default="whatsapp", nullable=False)
    status: Mapped[str] = mapped_column(
        String(16), default="draft", nullable=False
    )  # draft|confirmed|rejected
    confidence: Mapped[float] = mapped_column(Numeric(4, 2), default=1.00, nullable=False)

    raw_text: Mapped[str] = mapped_column(Text, nullable=False)
    parse_version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)

    # WhatsApp provenance
    chat_id: Mapped[str] = mapped_column(String(64), nullable=False)
    message_id: Mapped[Optional[str]] = mapped_column(String(128), index=True)

    user: Mapped[Optional[User]] = relationship(
        foreign_keys=[user_id], back_populates="expenses"
    )
    group: Mapped[Optional[Group]] = relationship(
        foreign_keys=[group_id], back_populates="expenses"
    )
    created_by: Mapped[Optional[User]] = relationship(
        foreign_keys=[created_by_user_id]
    )

    tags: Mapped[list[Tag]] = relationship(
        secondary="expense_tag",
        back_populates="expenses",
        lazy="selectin",
    )

    def __str__(self):
        tags = f" tags [{' '.join(tag.name for tag in self.tags)}]" if self.tags else ""
        return f"{self.currency} {self.amount} - {self.description or 'No description'}{tags}"


class Tag(Base, TimestampMixin):
    __tablename__ = "tag"
    __table_args__ = (UniqueConstraint("name", name="uq_tag_name"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    name: Mapped[str] = mapped_column(String(48), nullable=False)

    expenses: Mapped[list[Expense]] = relationship(
        secondary="expense_tag",
        back_populates="tags",
        lazy="selectin",
    )

    def __str__(self):
        return self.name
    
    def __repr__(self):
        return f"<Tag(name={self.name})>"


class ExpenseTag(Base):
    __tablename__ = "expense_tag"
    __table_args__ = (
        UniqueConstraint("expense_id", "tag_id", name="uq_expense_tag"),
        Index("ix_expense_tag_expense_id", "expense_id"),
        Index("ix_expense_tag_tag_id", "tag_id"),
    )

    expense_id: Mapped[int] = mapped_column(
        ForeignKey("expenses.id", ondelete="CASCADE"), primary_key=True
    )
    tag_id: Mapped[int] = mapped_column(
        ForeignKey("tag.id", ondelete="CASCADE"), primary_key=True
    )


class Budget(Base, TimestampMixin):
    __tablename__ = "budget"
    __table_args__ = (
        Index("ix_budget_user_id", "user_id"),
        Index("ix_budget_group_id", "group_id"),
        UniqueConstraint(
            "user_id", "group_id", "category_id", "period", name="uq_budget_scope"
        ),
        CheckConstraint(
            "(user_id IS NOT NULL) OR (group_id IS NOT NULL)",
            name="ck_budget_owner_scope",
        ),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)

    # Scope: usuario o grupo
    user_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.user_id", ondelete="CASCADE")
    )
    group_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("group_account.group_id", ondelete="CASCADE")
    )

    category_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("categories.id", ondelete="SET NULL")
    )
    amount: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False)
    period: Mapped[str] = mapped_column(
        String(16), default="monthly", nullable=False
    )  # monthly|weekly
    start_date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    user: Mapped[Optional[User]] = relationship(back_populates="budgets")
    group: Mapped[Optional[Group]] = relationship(back_populates="budgets")
    category: Mapped[Optional[Category]] = relationship()


# ---------- Message Log & Rules ----------

class MessageLog(Base, TimestampMixin):
    __tablename__ = "message_log"
    __table_args__ = (
        UniqueConstraint("provider", "provider_message_id", name="uq_msg_provider_msgid"),
        Index("ix_message_log_chat_id", "chat_id"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    provider: Mapped[str] = mapped_column(String(24), nullable=False)            # 'twilio' | 'meta'
    provider_message_id: Mapped[str] = mapped_column(String(128), nullable=False)
    chat_id: Mapped[str] = mapped_column(String(64), nullable=False)
    direction: Mapped[str] = mapped_column(String(3), default="in", nullable=False)  # in|out
    text: Mapped[Optional[str]] = mapped_column(Text)
    payload_json: Mapped[Optional[dict]] = mapped_column(JSONB)
    status: Mapped[str] = mapped_column(String(24), default="received", nullable=False)
    error: Mapped[Optional[str]] = mapped_column(Text)


class UserRule(Base, TimestampMixin):
    __tablename__ = "user_rule"
    __table_args__ = (Index("ix_user_rule_user_id", "user_id"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False
    )
    condition_json: Mapped[dict] = mapped_column(JSONB, nullable=False)  # e.g., {"contains": ["uber"]}
    action_json: Mapped[dict] = mapped_column(JSONB, nullable=False)     # e.g., {"category_id": 12}
    priority: Mapped[int] = mapped_column(Integer, default=100, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    user: Mapped[User] = relationship(back_populates="rules")
