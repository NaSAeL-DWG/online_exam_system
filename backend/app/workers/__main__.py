import argparse
import asyncio
import json
import logging
import sys

from app.core.config import get_settings
from app.core.database import Resources
from app.workers.recovery import recover_due_attempts


async def recover(limit: int | None) -> int:
    """运维恢复只读取 PostgreSQL 业务状态，Redis 失效时也可执行。"""

    settings = get_settings()
    resources = Resources(settings)
    try:
        result = await recover_due_attempts(
            resources, limit=limit or settings.attempt_scan_batch_size
        )
        print(json.dumps(result.to_dict(), ensure_ascii=False))
        return 1 if result.failed else 0
    except Exception as exc:
        # 只输出异常类型，避免连接字符串或凭据进入终端和运行记录。
        print(json.dumps({"error": type(exc).__name__}), file=sys.stderr)
        return 1
    finally:
        await resources.close()


def main() -> int:
    parser = argparse.ArgumentParser(description="在线考试独立后台运维入口")
    commands = parser.add_subparsers(dest="command", required=True)
    recovery = commands.add_parser("recover-attempts", help="补提交已经到期的有效作答")
    recovery.add_argument("--limit", type=int, choices=range(1, 1001), metavar="1..1000")
    worker = commands.add_parser("worker", help="运行独立 ARQ worker")
    worker.add_argument("--burst", action="store_true", help="启动恢复后处理当前队列并退出")
    args = parser.parse_args()
    if args.command == "recover-attempts":
        return asyncio.run(recover(args.limit))

    from arq.worker import create_worker
    from app.workers.attempts import WorkerSettings

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")
    # 一次性诊断不创建新的周期任务，常驻 worker 保持标准 cron 配置。
    options = {"burst": args.burst}
    if args.burst:
        options["cron_jobs"] = []
    instance = create_worker(WorkerSettings, **options)
    try:
        instance.run()
    except Exception as exc:
        print(json.dumps({"error": type(exc).__name__}), file=sys.stderr)
        return 1
    if args.burst:
        print(
            json.dumps(
                {
                    "startup_recovery": instance.ctx["startup_recovery"],
                    "jobs_complete": instance.jobs_complete,
                    "jobs_failed": instance.jobs_failed,
                },
                ensure_ascii=False,
            )
        )
    return 1 if instance.jobs_failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
