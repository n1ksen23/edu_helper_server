"""Private group applications."""

from alembic import op
import sqlalchemy as sa

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "group_requests",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("group_number", sa.String(50), nullable=False),
        sa.Column("contacts", sa.Text, nullable=False),
        sa.Column("status", sa.String(10), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("status IN ('pending', 'approved', 'rejected')"),
    )
    op.create_index("ix_group_requests_status_id", "group_requests", ["status", "id"])


def downgrade():
    op.drop_table("group_requests")
