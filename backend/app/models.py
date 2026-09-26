"""Alembic 模型注册入口；业务模块使用自己的模型与公开能力。"""

from app.modules.identity.models import *  # noqa: F403
from app.modules.teaching_class.models import *  # noqa: F403
from app.modules.auth.models import SessionCleanup  # noqa: F401
from app.modules.question.models import Question  # noqa: F401
