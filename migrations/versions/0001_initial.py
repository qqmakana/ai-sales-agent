"""initial schema

Revision ID: 0001_initial
Revises:
Create Date: 2026-02-02

"""
from alembic import op
import sqlalchemy as sa


revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("email", sa.String(length=120), nullable=False, unique=True),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("subscription_tier", sa.String(length=20), nullable=True),
        sa.Column("stripe_customer_id", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("automations_count", sa.Integer(), nullable=True),
    )

    op.create_table(
        "automations",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("goal", sa.String(length=500), nullable=False),
        sa.Column("recipient_email", sa.String(length=120), nullable=True),
        sa.Column("frequency", sa.String(length=50), nullable=True),
        sa.Column("scheduled_time", sa.String(length=20), nullable=True),
        sa.Column("scheduled_days", sa.String(length=100), nullable=True),
        sa.Column("end_date", sa.DateTime(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=True),
        sa.Column("last_run", sa.DateTime(), nullable=True),
        sa.Column("run_count", sa.Integer(), nullable=True),
        sa.Column("next_run_at", sa.DateTime(), nullable=True),
        sa.Column("locked_at", sa.DateTime(), nullable=True),
        sa.Column("status", sa.String(length=50), nullable=True),
        sa.Column("result", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
    )

    op.create_table(
        "integrations",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("service_name", sa.String(length=50), nullable=False),
        sa.Column("credentials_json", sa.Text(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
    )

    op.create_table(
        "leads",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("email", sa.String(length=120), nullable=False),
        sa.Column("website", sa.String(length=200), nullable=True),
        sa.Column("niche", sa.String(length=100), nullable=True),
        sa.Column("status", sa.String(length=50), nullable=True),
        sa.Column("is_unlocked", sa.Boolean(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
    )


def downgrade():
    op.drop_table("leads")
    op.drop_table("integrations")
    op.drop_table("automations")
    op.drop_table("users")
