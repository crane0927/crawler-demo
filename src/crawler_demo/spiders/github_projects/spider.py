from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlencode

from crawler_demo.core.base import BaseSpider
from crawler_demo.core.exceptions import CrawlerError
from crawler_demo.core.http import get_json


@dataclass(slots=True)
class GitHubProjectsSpiderConfig:
    query: str
    limit: int = 10
    sort: str = "stars"
    order: str = "desc"
    per_page: int = 10


class GitHubProjectsSpider(BaseSpider):
    name = "github_projects"

    def __init__(self, token: str | None = None) -> None:
        self.token = token or os.getenv("GITHUB_TOKEN")

    def run(self, args: dict[str, Any]) -> list[dict[str, Any]]:
        config = self._build_config(args)
        per_page = min(max(config.per_page, 1), 100, config.limit)
        params = {
            "q": config.query,
            "sort": config.sort,
            "order": config.order,
            "per_page": per_page,
        }
        url = f"https://api.github.com/search/repositories?{urlencode(params)}"
        payload = get_json(url=url, headers=self._build_headers(), timeout=30)
        items = payload.get("items", [])

        # 统一在 spider 内完成字段裁剪，保证上层命令行和后续存储逻辑只处理标准结构。
        return [self._normalize_repository(item) for item in items[: config.limit]]

    def _build_config(self, args: dict[str, Any]) -> GitHubProjectsSpiderConfig:
        limit = int(args.get("limit", 10))
        if limit <= 0:
            raise CrawlerError("limit 必须大于 0")

        query = str(args.get("query", "")).strip()
        if not query:
            raise CrawlerError("query 不能为空")

        return GitHubProjectsSpiderConfig(
            query=query,
            limit=limit,
            sort=str(args.get("sort", "stars")),
            order=str(args.get("order", "desc")),
            per_page=limit,
        )

    def _build_headers(self) -> dict[str, str]:
        headers = {
            "Accept": "application/vnd.github+json",
            "User-Agent": "crawler-demo",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        return headers

    def _normalize_repository(self, item: dict[str, Any]) -> dict[str, Any]:
        owner = item.get("owner") or {}
        return {
            "name": item.get("name"),
            "full_name": item.get("full_name"),
            "html_url": item.get("html_url"),
            "description": item.get("description"),
            "language": item.get("language"),
            "stargazers_count": item.get("stargazers_count"),
            "forks_count": item.get("forks_count"),
            "open_issues_count": item.get("open_issues_count"),
            "watchers_count": item.get("watchers_count"),
            "created_at": item.get("created_at"),
            "updated_at": item.get("updated_at"),
            "pushed_at": item.get("pushed_at"),
            "topics": item.get("topics", []),
            "owner": {
                "login": owner.get("login"),
                "html_url": owner.get("html_url"),
            },
        }
