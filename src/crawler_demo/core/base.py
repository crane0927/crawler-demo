from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class BaseSpider(ABC):
    """所有具体 spider 的公共基类。"""

    name: str

    @abstractmethod
    def run(self, args: dict[str, Any]) -> list[dict[str, Any]]:
        """执行抓取并返回标准化后的结果列表。"""

