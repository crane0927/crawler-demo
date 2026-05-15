from __future__ import annotations

import json
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from crawler_demo.core.exceptions import CrawlerError


def get_json(url: str, headers: dict[str, str], timeout: int = 30) -> dict[str, Any]:
    request = Request(url, headers=headers, method="GET")

    try:
        with urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        raise CrawlerError(build_http_error_message(exc)) from exc
    except URLError as exc:
        raise CrawlerError(f"网络请求失败: {exc.reason}") from exc
    except TimeoutError as exc:
        raise CrawlerError("请求超时") from exc


def build_http_error_message(exc: HTTPError) -> str:
    status = getattr(exc, "code", "unknown")
    body = ""

    # 尽量保留服务端返回的错误信息，方便定位限流、鉴权或参数错误问题。
    try:
        raw = exc.read().decode("utf-8")
        data = json.loads(raw)
        body = data.get("message", raw)
    except Exception:
        body = str(exc)

    return f"HTTP 请求失败，状态码 {status}: {body}"
