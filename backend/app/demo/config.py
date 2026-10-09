import os
import re
from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class DemoConfig:
    namespace: str
    admin_login: str
    admin_password: str = field(repr=False)
    password: str = field(repr=False)
    manifest_path: Path
    stage: str = "complete"
    window_seconds: int = 120

    def __post_init__(self):
        if not re.fullmatch(r"[a-z0-9][a-z0-9-]{3,31}", self.namespace):
            raise ValueError("namespace 须为4—32个小写字母、数字或连字符")
        if not self.admin_login or not self.admin_password or len(self.password) < 10:
            raise ValueError("需要管理员凭据及至少10位的 DEMO_PASSWORD")
        if self.stage not in {"identities", "complete"}:
            raise ValueError("stage 只能是 identities 或 complete")
        if self.window_seconds < 30:
            raise ValueError("历史考试窗口至少30秒，请为首次运行留足时间")

    @classmethod
    def from_environment(cls, args):
        """凭据仅从运行环境读取，不接收密码命令行参数。"""
        return cls(
            namespace=args.namespace,
            admin_login=os.getenv("DEMO_ADMIN_LOGIN") or os.getenv("ADMIN_LOGIN_NAME", ""),
            admin_password=os.getenv("DEMO_ADMIN_PASSWORD") or os.getenv("ADMIN_PASSWORD", ""),
            password=os.getenv("DEMO_PASSWORD", ""),
            manifest_path=Path(args.manifest),
            stage=args.stage,
            window_seconds=args.window_seconds,
        )
