"""Initial database setup with user handling tables

Revision ID: 20250811_user_handling
Revises: 
Create Date: 2025-08-11 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
import enum

# revision identifiers, used by Alembic.
revision = '20250811_user_handling'
down_revision = None
branch_labels = None
depends_on = None

class RoleEnum(enum.Enum):
    user = "user"
    admin = "admin"

def upgrade() -> None:
    op.create_table(
        'users',
        sa.Column('user_id', sa.Integer, primary_key=True),
        sa.Column('phone_e164', sa.String, unique=True, nullable=False),
        sa.Column('wa_user_id', sa.Text, nullable=True),
        sa.Column('display_name', sa.Text, nullable=True),
        sa.Column('locale', sa.Text, default='es-CL'),
        sa.Column('timezone', sa.Text, default='America/Santiago'),
        sa.Column('currency', sa.Text, default='CLP'),
        sa.Column('is_active', sa.Boolean, default=True),
        sa.Column('is_blocked', sa.Boolean, default=False),
        sa.Column('created_at', sa.DateTime),
        sa.Column('last_seen_at', sa.DateTime),
    )
    op.create_table(
        'consents',
        sa.Column('consent_id', sa.Integer, primary_key=True),
        sa.Column('user_id', sa.Integer, sa.ForeignKey('users.user_id')),
        sa.Column('type', sa.Text),
        sa.Column('granted_at', sa.DateTime),
        sa.Column('revoked_at', sa.DateTime, nullable=True),
        sa.UniqueConstraint('user_id', 'type', 'granted_at'),
    )
    op.create_table(
        'sessions',
        sa.Column('session_id', sa.Integer, primary_key=True),
        sa.Column('user_id', sa.Integer, sa.ForeignKey('users.user_id')),
        sa.Column('state', sa.Text),
        sa.Column('last_input', sa.Text, nullable=True),
        sa.Column('started_at', sa.DateTime),
        sa.Column('updated_at', sa.DateTime),
    )
    op.create_table(
        'user_roles',
        sa.Column('user_id', sa.Integer, sa.ForeignKey('users.user_id'), primary_key=True),
        sa.Column('role', sa.Enum(RoleEnum), default=RoleEnum.user),
    )

def downgrade() -> None:
    op.drop_table('user_roles')
    op.drop_table('sessions')
    op.drop_table('consents')
    op.drop_table('users')
