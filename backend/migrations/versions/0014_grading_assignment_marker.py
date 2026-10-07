"""持久记录待初分配考试，使周期恢复扫描只读取待办。"""

from alembic import op
import sqlalchemy as sa

revision = "0014_grading_assignment_marker"
down_revision = "0013_result_withdrawal"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "exam",
        sa.Column(
            "grading_assignment_pending", sa.Boolean(), nullable=False, server_default=sa.false()
        ),
    )
    # 仅迁移中回填既有有效简答场次；恢复完成后业务用例清除待办标记。
    op.execute("""
        UPDATE exam SET grading_assignment_pending = true
        WHERE status = 'RELEASED'
          AND EXISTS (
              SELECT 1 FROM exam_question
              WHERE exam_question.exam_id = exam.id AND type = 'SHORT_ANSWER'
          )
          AND (
              end_at > CURRENT_TIMESTAMP OR EXISTS (
                  SELECT 1 FROM exam_attempt
                  JOIN exam_participant ON exam_participant.id = exam_attempt.exam_participant_id
                  WHERE exam_participant.exam_id = exam.id
                    AND exam_participant.status = 'ASSIGNED'
                    AND exam_attempt.status != 'VOID'
                    AND (
                        exam_attempt.status = 'IN_PROGRESS'
                        OR exam_attempt.grading_status = 'PENDING'
                        OR (
                            exam_attempt.grading_status = 'GRADING'
                            AND NOT EXISTS (
                                SELECT 1 FROM grading_task
                                WHERE grading_task.attempt_id = exam_attempt.id
                            )
                        )
                    )
              )
          )
    """)
    op.alter_column("exam", "grading_assignment_pending", server_default=None)
    op.create_index(
        "ix_exam_grading_assignment_pending",
        "exam",
        ["end_at"],
        postgresql_where=sa.text("grading_assignment_pending = true"),
    )


def downgrade():
    op.drop_index("ix_exam_grading_assignment_pending", table_name="exam")
    op.drop_column("exam", "grading_assignment_pending")
