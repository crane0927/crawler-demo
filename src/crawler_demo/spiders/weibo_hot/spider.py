from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from urllib.parse import quote

from crawler_demo.core.base import BaseSpider
from crawler_demo.core.exceptions import CrawlerError
from crawler_demo.core.http import get_json


@dataclass(slots=True)
class WeiboHotSpiderConfig:
    limit: int = 10


class WeiboHotSpider(BaseSpider):
    name = "weibo_hot"

    def run(self, args: dict[str, Any]) -> list[dict[str, Any]]:
        config = self._build_config(args)
        payload = get_json(
            url="https://weibo.com/ajax/side/hotSearch",
            headers=self._build_headers(),
            timeout=30,
        )
        data = payload.get("data") or {}
        realtime_items = data.get("realtime") or []
        if not realtime_items:
            raise CrawlerError("微博热榜返回为空，可能是接口结构变化或请求被限制")

        # 微博热点榜可能混入广告或结构不完整的数据，这里统一做字段收敛和数量截断。
        normalized_items = [
            self._normalize_item(item)
            for item in realtime_items[: config.limit]
            if item.get("word") or item.get("note")
        ]
        return normalized_items

    def _build_config(self, args: dict[str, Any]) -> WeiboHotSpiderConfig:
        limit = int(args.get("limit", 10))
        if limit <= 0:
            raise CrawlerError("limit 必须大于 0")

        return WeiboHotSpiderConfig(limit=limit)

    def _build_headers(self) -> dict[str, str]:
        return {
            "Accept": "application/json, text/plain, */*",
            "Referer": "https://weibo.com/",
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/136.0.0.0 Safari/537.36"
            ),
            "X-Requested-With": "XMLHttpRequest",
        }

    def _normalize_item(self, item: dict[str, Any]) -> dict[str, Any]:
        keyword = item.get("word") or item.get("note") or ""
        keyword_scheme = item.get("word_scheme") or keyword
        encoded_keyword = quote(keyword_scheme, safe="")
        return {
            "title": keyword,
            "rank": item.get("realpos") or item.get("rank"),
            "hot_value": item.get("num"),
            "label": item.get("label_name") or item.get("icon_desc") or "",
            "topic_flag": item.get("topic_flag"),
            "url": f"https://s.weibo.com/weibo?q={encoded_keyword}",
            "raw_keyword": keyword_scheme,
        }
