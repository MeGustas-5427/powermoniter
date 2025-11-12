"""重连退避策略工具。"""

from __future__ import annotations

from dataclasses import dataclass
import asyncio


@dataclass(frozen=True)
class RetryPolicy:
    """定义指数退避策略。"""

    base_delay: float = 1.0
    max_delay: float = 60.0
    max_attempts: int = 12

    def next_delay(self, attempt: int) -> float:
        """根据尝试次数返回等待秒数，超过最大次数抛出异常。"""

        if attempt < 1:
            raise ValueError("attempt 必须大于等于 1")
        if attempt > self.max_attempts:
            raise RuntimeError("超过最大重试次数")

        delay = self.base_delay * (2 ** (attempt - 1))
        return min(delay, self.max_delay)

    async def wait_with_retry(self, attempt: int) -> None:
        """按照退避策略等待对应秒数。"""

        delay = self.next_delay(attempt)
        await asyncio.sleep(delay)


