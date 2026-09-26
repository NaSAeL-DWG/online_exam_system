"""独立考试资格与撤回/撤销所需的真实作答持久化基础。"""

from alembic import op
import sqlalchemy as sa

revision = "0008_participants_attempts"
down_revision = "0007_exam_graders"
branch_labels = None
depends_on = None


def timestamps():
    return [
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    ]


def upgrade():
    op.create_table(
        "exam_participant",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("exam_id", sa.UUID(), sa.ForeignKey("exam.id"), nullable=False),
        sa.Column("user_id", sa.UUID(), sa.ForeignKey("user_account.id"), nullable=False),
        sa.Column(
            "status", sa.Enum("ASSIGNED", "CANCELLED", name="participant_status"), nullable=False
        ),
        sa.Column("assigned_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("cancelled_at", sa.DateTime(timezone=True)),
        sa.Column("cancelled_reason", sa.Text()),
        sa.Column("version", sa.BigInteger(), nullable=False),
        *timestamps(),
        sa.UniqueConstraint("exam_id", "user_id"),
    )
    op.create_index(
        "ix_participant_user_status_exam", "exam_participant", ["user_id", "status", "exam_id"]
    )
    op.create_index("ix_participant_exam_status", "exam_participant", ["exam_id", "status"])
    op.create_table(
        "exam_attempt",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column(
            "exam_participant_id", sa.UUID(), sa.ForeignKey("exam_participant.id"), nullable=False
        ),
        sa.Column("attempt_no", sa.Integer(), nullable=False),
        sa.Column(
            "status",
            sa.Enum("IN_PROGRESS", "SUBMITTED", "VOID", name="attempt_status"),
            nullable=False,
        ),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deadline_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("voided_at", sa.DateTime(timezone=True)),
        sa.Column("void_reason", sa.Text()),
        sa.Column("version", sa.Integer(), nullable=False),
        *timestamps(),
        sa.UniqueConstraint("exam_participant_id", "attempt_no"),
        sa.CheckConstraint("attempt_no > 0"),
    )
    op.create_index(
        "uq_attempt_in_progress",
        "exam_attempt",
        ["exam_participant_id"],
        unique=True,
        postgresql_where=sa.text("status = 'IN_PROGRESS'::attempt_status"),
    )
    op.create_index(
        "ix_attempt_deadline",
        "exam_attempt",
        ["deadline_at"],
        postgresql_where=sa.text("status = 'IN_PROGRESS'::attempt_status"),
    )


def downgrade():
    op.drop_table("exam_attempt")
    op.drop_table("exam_participant")
    for name in ("attempt_status", "participant_status"):
        sa.Enum(name=name).drop(op.get_bind())
