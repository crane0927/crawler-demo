from __future__ import annotations

import hashlib
import http.client
import mimetypes
import re
from collections import deque
from dataclasses import dataclass
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qsl, quote, urlencode, urljoin, urlparse, urlunparse
from urllib.request import Request, urlopen

from crawler_demo.core.base import BaseSpider
from crawler_demo.core.exceptions import CrawlerError

RESOURCE_EXTENSIONS = {
    ".jpg",
    ".jpeg",
    ".png",
    ".gif",
    ".svg",
    ".webp",
    ".ico",
    ".pdf",
    ".zip",
    ".rar",
    ".7z",
    ".tar",
    ".gz",
    ".doc",
    ".docx",
    ".xls",
    ".xlsx",
    ".ppt",
    ".pptx",
    ".mp4",
    ".mp3",
    ".avi",
    ".txt",
}
SKIP_SCHEMES = {"javascript", "mailto", "tel", "data"}
HTML_EXTENSIONS = {".html", ".htm", ".shtml", ".php", ".asp", ".aspx", ".jsp"}


@dataclass
class FetchResult:
    url: str
    status_code: int
    content_type: str
    body: bytes


@dataclass
class SiteMirrorSpiderConfig:
    start_url: str
    max_pages: int = 2000
    timeout: int = 20
    output_dir: str = "output/site_mirror"
    resources_dir: str = "output/site_mirror/resources"
    allowed_domain: str = ""


class SiteMirrorHtmlPageParser(HTMLParser):
    def __init__(self, base_url: str) -> None:
        super().__init__(convert_charrefs=True)
        self.base_url = base_url
        self.title = ""
        self.meta_keywords = ""
        self.meta_description = ""
        self.links: list[str] = []
        self.resources: list[str] = []
        self.text_chunks: list[str] = []
        self._ignored_stack: list[str] = []
        self._inside_title = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attr_map = {key.lower(): value or "" for key, value in attrs}
        normalized_tag = tag.lower()

        if normalized_tag in {"script", "style", "noscript"}:
            self._ignored_stack.append(normalized_tag)
            return

        if normalized_tag == "title":
            self._inside_title = True

        if normalized_tag == "meta":
            self._handle_meta(attr_map)
            return

        if normalized_tag == "a":
            href = attr_map.get("href", "").strip()
            if href:
                self.links.append(urljoin(self.base_url, href))
            return

        resource_attr = self._pick_resource_attr(normalized_tag, attr_map)
        if resource_attr:
            self.resources.append(urljoin(self.base_url, resource_attr))

    def handle_endtag(self, tag: str) -> None:
        normalized_tag = tag.lower()
        if normalized_tag == "title":
            self._inside_title = False
        if self._ignored_stack and normalized_tag == self._ignored_stack[-1]:
            self._ignored_stack.pop()

    def handle_data(self, data: str) -> None:
        if self._ignored_stack:
            return

        cleaned = " ".join(data.split())
        if not cleaned:
            return

        if self._inside_title:
            self.title = f"{self.title} {cleaned}".strip()
        self.text_chunks.append(cleaned)

    def _handle_meta(self, attr_map: dict[str, str]) -> None:
        meta_name = attr_map.get("name", "").strip().lower()
        content = attr_map.get("content", "").strip()
        if meta_name == "keywords":
            self.meta_keywords = content
        if meta_name == "description":
            self.meta_description = content

    def _pick_resource_attr(
        self, tag_name: str, attr_map: dict[str, str]
    ) -> str | None:
        if tag_name in {"img", "script", "iframe", "embed", "source"}:
            return attr_map.get("src", "").strip() or None
        if tag_name == "link":
            return attr_map.get("href", "").strip() or None
        return None


class SiteMirrorSpider(BaseSpider):
    name = "site_mirror"

    def run(self, args: dict[str, Any]) -> dict[str, Any]:
        config = self._build_config(args)
        pages: list[dict[str, Any]] = []
        resources: list[dict[str, Any]] = []
        errors: list[dict[str, Any]] = []
        page_queue = deque([self._normalize_url(config.start_url)])
        seen_pages: set[str] = set()
        seen_resources: set[str] = set()

        while page_queue and len(pages) < config.max_pages:
            current_url = page_queue.popleft()
            if current_url in seen_pages:
                continue
            seen_pages.add(current_url)

            try:
                fetch_result = self._fetch_url(current_url, timeout=config.timeout)
            except CrawlerError as exc:
                # 单个页面失败时记录错误并继续，避免整站抓取被局部异常直接打断。
                errors.append(
                    {
                        "url": current_url,
                        "error": str(exc),
                        "failed_at": self._now_iso(),
                    }
                )
                continue

            if not self._is_html_content_type(fetch_result.content_type):
                continue

            page_record = self._extract_page_record(
                url=fetch_result.url,
                html=self._decode_body(fetch_result.body, fetch_result.content_type),
                status_code=fetch_result.status_code,
            )
            pages.append(page_record)

            for discovered_page in page_record["links"]:
                if (
                    discovered_page not in seen_pages
                    and self._should_follow_page(
                        discovered_page, allowed_domain=config.allowed_domain
                    )
                ):
                    page_queue.append(discovered_page)

            for resource_url in page_record["resources"]:
                normalized_resource = self._normalize_url(resource_url)
                if normalized_resource in seen_resources:
                    continue
                seen_resources.add(normalized_resource)
                resource_record = self._download_resource(
                    resource_url=normalized_resource,
                    resources_dir=Path(config.resources_dir),
                    timeout=config.timeout,
                )
                if resource_record is not None:
                    resources.append(resource_record)

        return {
            "site": {
                # 站点名称优先使用域名，避免把 spider 与某个具体业务站点强绑定。
                "name": config.allowed_domain,
                "start_url": config.start_url,
                "allowed_domain": config.allowed_domain,
                "crawled_at": self._now_iso(),
            },
            "pages": pages,
            "resources": resources,
            "errors": errors,
            "stats": {
                "pages_crawled": len(pages),
                "resources_downloaded": len(resources),
                "page_errors": len(errors),
                "pages_discovered": len(seen_pages),
            },
        }

    def _build_config(self, args: dict[str, Any]) -> SiteMirrorSpiderConfig:
        start_url = self._normalize_url(
            str(args.get("start_url") or "http://www.qheze.com/").strip()
        )
        parsed = urlparse(start_url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise CrawlerError("start_url 必须是合法的 http/https 地址")

        max_pages = int(args.get("max_pages", 2000))
        timeout = int(args.get("timeout", 20))
        output_dir = str(args.get("output_dir") or "output/site_mirror").strip()
        resources_dir = str(args.get("resources_dir") or f"{output_dir}/resources").strip()

        if max_pages <= 0:
            raise CrawlerError("max_pages 必须大于 0")
        if timeout <= 0:
            raise CrawlerError("timeout 必须大于 0")

        return SiteMirrorSpiderConfig(
            start_url=start_url,
            max_pages=max_pages,
            timeout=timeout,
            output_dir=output_dir,
            resources_dir=resources_dir,
            allowed_domain=parsed.netloc.lower(),
        )

    def _extract_page_record(
        self, url: str, html: str, status_code: int
    ) -> dict[str, Any]:
        parser = SiteMirrorHtmlPageParser(base_url=url)
        parser.feed(html)

        normalized_links = sorted(
            {
                self._normalize_url(link)
                for link in parser.links
                if self._normalize_url(link)
            }
        )
        normalized_resources = sorted(
            {
                self._normalize_url(resource)
                for resource in parser.resources + parser.links
                if self._is_resource_url(resource)
            }
        )

        return {
            "url": self._normalize_url(url),
            "status_code": status_code,
            "title": parser.title.strip(),
            "meta": {
                "keywords": parser.meta_keywords,
                "description": parser.meta_description,
            },
            # 统一压平成纯文本，方便后续搜索、存储和离线分析。
            "text": "\n".join(parser.text_chunks),
            "links": normalized_links,
            "resources": normalized_resources,
            "crawled_at": self._now_iso(),
        }

    def _fetch_url(self, url: str, timeout: int) -> FetchResult:
        request = Request(
            self._build_request_url(url),
            headers=self._build_headers(),
            method="GET",
        )
        try:
            with urlopen(request, timeout=timeout) as response:
                content_type = response.headers.get("Content-Type", "")
                status_code = getattr(response, "status", 200)
                return FetchResult(
                    url=response.geturl(),
                    status_code=status_code,
                    content_type=content_type,
                    body=response.read(),
                )
        except HTTPError as exc:
            raise CrawlerError(f"请求 {url} 失败，状态码 {exc.code}") from exc
        except URLError as exc:
            raise CrawlerError(f"请求 {url} 失败: {exc.reason}") from exc
        except TimeoutError as exc:
            raise CrawlerError(f"请求 {url} 超时") from exc
        except http.client.HTTPException as exc:
            raise CrawlerError(f"请求 {url} 失败: {exc}") from exc

    def _download_resource(
        self, resource_url: str, resources_dir: Path, timeout: int
    ) -> dict[str, Any] | None:
        try:
            fetch_result = self._fetch_url(resource_url, timeout=timeout)
        except CrawlerError:
            # 资源下载失败不应中断整站抓取，这里只跳过失败资源，保证主体页面尽量完整。
            return None

        suffix = self._guess_suffix(fetch_result.url, fetch_result.content_type)
        file_name = self._build_resource_file_name(fetch_result.url, suffix)
        resources_dir.mkdir(parents=True, exist_ok=True)
        file_path = resources_dir / file_name
        file_path.write_bytes(fetch_result.body)

        return {
            "url": self._normalize_url(fetch_result.url),
            "content_type": fetch_result.content_type,
            "size": len(fetch_result.body),
            "saved_path": str(file_path),
            "downloaded_at": self._now_iso(),
        }

    def _build_headers(self) -> dict[str, str]:
        return {
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/136.0.0.0 Safari/537.36"
            ),
            "Accept": "*/*",
        }

    def _build_request_url(self, url: str) -> str:
        parsed = urlparse(url)
        # 请求前统一做路径与查询编码，避免站点包含中文或空格时在 http.client 层抛出 ASCII 编码异常。
        encoded_path = quote(parsed.path or "/", safe="/%:@!$&'()*+,;=-._~")
        encoded_query = urlencode(parse_qsl(parsed.query, keep_blank_values=True), doseq=True)
        return urlunparse(
            parsed._replace(
                path=encoded_path,
                query=encoded_query,
            )
        )

    def _normalize_url(self, url: str) -> str:
        trimmed = (url or "").strip()
        if not trimmed:
            return ""

        parsed = urlparse(trimmed)
        if parsed.scheme.lower() in SKIP_SCHEMES:
            return ""
        if not parsed.scheme:
            return ""

        normalized_path = parsed.path or "/"
        if normalized_path.endswith("/index.html") or normalized_path.endswith("/index.htm"):
            normalized_path = normalized_path.rsplit("/", 1)[0] + "/"

        normalized_path = re.sub(r"/{2,}", "/", normalized_path)
        query = urlencode(sorted(parse_qsl(parsed.query, keep_blank_values=True)))
        normalized = parsed._replace(
            scheme=parsed.scheme.lower(),
            netloc=parsed.netloc.lower(),
            path=normalized_path,
            params="",
            query=query,
            fragment="",
        )
        return urlunparse(normalized)

    def _should_follow_page(self, url: str, allowed_domain: str) -> bool:
        normalized = self._normalize_url(url)
        if not normalized:
            return False

        parsed = urlparse(normalized)
        if parsed.netloc.lower() != allowed_domain.lower():
            return False
        if self._is_resource_url(normalized):
            return False

        path = parsed.path or "/"
        suffix = Path(path).suffix.lower()
        return not suffix or suffix in HTML_EXTENSIONS

    def _is_resource_url(self, url: str) -> bool:
        normalized = self._normalize_url(url)
        if not normalized:
            return False
        suffix = Path(urlparse(normalized).path).suffix.lower()
        return suffix in RESOURCE_EXTENSIONS

    def _is_html_content_type(self, content_type: str) -> bool:
        lowered = content_type.lower()
        return "text/html" in lowered or "application/xhtml+xml" in lowered

    def _decode_body(self, body: bytes, content_type: str) -> str:
        charset_match = re.search(r"charset=([a-zA-Z0-9_-]+)", content_type)
        encodings = [charset_match.group(1)] if charset_match else []
        encodings.extend(["utf-8", "gb18030"])

        for encoding in encodings:
            try:
                return body.decode(encoding)
            except UnicodeDecodeError:
                continue
        return body.decode("utf-8", errors="ignore")

    def _guess_suffix(self, url: str, content_type: str) -> str:
        suffix = Path(urlparse(url).path).suffix.lower()
        if suffix:
            return suffix
        guessed = mimetypes.guess_extension(content_type.split(";")[0].strip())
        return guessed or ".bin"

    def _build_resource_file_name(self, url: str, suffix: str) -> str:
        parsed = urlparse(url)
        base_name = Path(parsed.path).stem or "resource"
        safe_name = re.sub(r"[^a-zA-Z0-9_-]+", "_", base_name).strip("_") or "resource"
        digest = hashlib.sha1(url.encode("utf-8")).hexdigest()[:12]
        return f"{safe_name}_{digest}{suffix}"

    def _now_iso(self) -> str:
        return datetime.now(timezone.utc).isoformat()
