from logging.handlers import RotatingFileHandler
from pathlib import Path
import logging


class ByteRotatingHandler(RotatingFileHandler):
    def shouldRollover(self, record):
        # 标准处理器以字符数预估；中文记录必须按真实 UTF-8 字节约束单文件10MB。
        if self.stream is None:
            self.stream = self._open()
        self.stream.seek(0, 2)
        size = len((self.format(record) + self.terminator).encode("utf-8"))
        return self.stream.tell() + size > self.maxBytes


def write_batch(directory, records):
    """调用方持有数据库全局写锁；每批重新打开文件，避免其他进程轮转后持有旧 inode。"""
    folder = Path(directory).resolve()
    folder.mkdir(parents=True, exist_ok=True)
    handler = ByteRotatingHandler(
        folder / "runtime.log",
        maxBytes=10 * 1024 * 1024,
        backupCount=4,
        encoding="utf-8",
        delay=True,
    )

    # logging 默认会吞掉磁盘写入错误，改为交由批量用例记录固定安全错误。
    def propagate_error(record):
        raise OSError("日志文件写入失败")

    handler.handleError = propagate_error
    handler.setFormatter(logging.Formatter("%(message)s"))
    try:
        for record in records:
            line = f"{record.timestamp.isoformat()} {record.level}: [{record.module}]({record.task}): {record.message}"
            handler.emit(logging.LogRecord("runtime", logging.INFO, "", 0, line, (), None))
        handler.flush()
    finally:
        handler.close()
