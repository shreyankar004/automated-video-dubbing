
from __future__ import annotations

import logging
import sys
from contextvars import ContextVar

_job_id_ctx: ContextVar[str] = ContextVar("job_id", default="-")


class JobIdFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.job_id = _job_id_ctx.get()
        return True


def set_job_context(job_id: str | None) -> None:
    _job_id_ctx.set(job_id or "-")


def configure_logging(level: int = logging.INFO) -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(
        logging.Formatter(
            fmt="%(asctime)s [%(levelname)s] [job=%(job_id)s] %(name)s: %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
    )
    handler.addFilter(JobIdFilter())

    root = logging.getLogger()
    root.setLevel(level)
    root.handlers.clear()
    root.addHandler(handler)


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
