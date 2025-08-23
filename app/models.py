from sqlalchemy import Column, String, Integer, Boolean, DateTime, ForeignKey, Enum, UniqueConstraint, Text
from sqlalchemy.ext.declarative import declarative_base
import enum

Base = declarative_base()

class RoleEnum(enum.Enum):
    user = "user"
    admin = "admin"

class User(Base):
    __tablename__ = "users"
    user_id = Column(Integer, primary_key=True)
    phone_e164 = Column(String, unique=True, nullable=False)
    wa_user_id = Column(Text, nullable=True)
    display_name = Column(Text, nullable=True)
    locale = Column(Text, default="es-CL")
    timezone = Column(Text, default="America/Santiago")
    currency = Column(Text, default="CLP")
    is_active = Column(Boolean, default=True)
    is_blocked = Column(Boolean, default=False)
    created_at = Column(DateTime)
    last_seen_at = Column(DateTime)

class Consent(Base):
    __tablename__ = "consents"
    consent_id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.user_id"))
    type = Column(Text)
    granted_at = Column(DateTime)
    revoked_at = Column(DateTime, nullable=True)
    __table_args__ = (UniqueConstraint("user_id", "type", "granted_at"),)

class Session(Base):
    __tablename__ = "sessions"
    session_id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.user_id"))
    state = Column(Text)
    last_input = Column(Text, nullable=True)
    started_at = Column(DateTime)
    updated_at = Column(DateTime)

class UserRole(Base):
    __tablename__ = "user_roles"
    user_id = Column(Integer, ForeignKey("users.user_id"), primary_key=True)
    role = Column(Enum(RoleEnum), default=RoleEnum.user)
