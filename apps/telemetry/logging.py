"""统一日志获取入口，附带上下文字段。"""

from __future__ import annotations

import logging
from typing import Any, Dict


class ContextLogger(logging.LoggerAdapter):
    """简单的 LoggerAdapter，确保 extra 字段被合并。"""

    def process(self, msg: str, kwargs: Dict[str, Any]):
        extra = kwargs.pop("extra", {})
        merged = {**self.extra, **extra}
        if merged:
            kwargs["extra"] = merged
        return msg, kwargs


def get_logger(name: str, **context: Any) -> ContextLogger:
    """返回绑定给定上下文的 LoggerAdapter。"""

    logger = logging.getLogger(name)
    return ContextLogger(logger, context or {})


__all__ = ["get_logger"]
