"""授权访问的不可变图片资源。"""

from alembic import op
import sqlalchemy as sa

revision = "0004_assets"
down_revision = "0003_questions"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "uploaded_asset",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("uploader_id", sa.UUID(), sa.ForeignKey("user_account.id"), nullable=False),
        sa.Column("storage_key", sa.String(100), unique=True, nullable=False),
        sa.Column("original_name", sa.String(255), nullable=False),
        sa.Column("media_type", sa.String(100), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade():
    op.drop_table("uploaded_asset")
