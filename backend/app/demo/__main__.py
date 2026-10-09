import argparse
import asyncio
import json
import sys

from .config import DemoConfig
from .http import DemoError, HTTPTransport
from .runner import run_demo


def main():
    parser = argparse.ArgumentParser(description="通过公开接口准备可重跑的在线考试演示数据")
    parser.add_argument("--base-url", default="http://127.0.0.1:18000")
    parser.add_argument("--namespace", default="demo-v1")
    parser.add_argument("--manifest", default="../.local/demo-v1.json")
    parser.add_argument("--stage", choices=["identities", "complete"], default="complete")
    parser.add_argument("--window-seconds", type=int, default=120)
    args = parser.parse_args()
    try:
        config = DemoConfig.from_environment(args)
        report = asyncio.run(run_demo(config, HTTPTransport(args.base_url)))
    except (DemoError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(1) from None
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
