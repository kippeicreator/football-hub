#!/usr/bin/env python3
"""Validate the static pages and crawl files used by Football Hub."""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlsplit
from xml.etree import ElementTree


ROOT = Path(__file__).resolve().parents[1]
BASE_URL = "https://kippeicreator.github.io/worldcup2026/"


@dataclass
class ValidationTotals:
    html_pages: int = 0
    json_ld_blocks: int = 0
    internal_links: int = 0
    sitemap_urls: int = 0


class PageParser(HTMLParser):
    """Collect the small set of HTML details needed for static validation."""

    def __init__(self) -> None:
        super().__init__()
        self.html_lang: str | None = None
        self.title_parts: list[str] = []
        self.in_title = False
        self.descriptions: list[str | None] = []
        self.canonicals: list[str | None] = []
        self.hrefs: list[tuple[str, int, str]] = []
        self.json_ld_blocks: list[str] = []
        self.current_json_ld: list[str] | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = dict(attrs)

        if tag == "html":
            self.html_lang = attributes.get("lang")
        elif tag == "title":
            self.in_title = True
        elif tag == "meta" and attributes.get("name", "").lower() == "description":
            self.descriptions.append(attributes.get("content"))
        elif tag == "link":
            rel_values = attributes.get("rel", "").lower().split()
            if "canonical" in rel_values:
                self.canonicals.append(attributes.get("href"))
        elif tag == "script" and attributes.get("type", "").lower() == "application/ld+json":
            self.current_json_ld = []

        href = attributes.get("href")
        if href is not None:
            self.hrefs.append((href, self.getpos()[0], tag))

    def handle_endtag(self, tag: str) -> None:
        if tag == "title":
            self.in_title = False
        elif tag == "script" and self.current_json_ld is not None:
            self.json_ld_blocks.append("".join(self.current_json_ld))
            self.current_json_ld = None

    def handle_data(self, data: str) -> None:
        if self.in_title:
            self.title_parts.append(data)
        if self.current_json_ld is not None:
            self.current_json_ld.append(data)


def public_pages() -> list[Path]:
    """Return every index page published from the repository root."""

    return sorted(
        page
        for page in ROOT.rglob("index.html")
        if ".git" not in page.parts and "__pycache__" not in page.parts
    )


def display_path(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def is_ignored_href(href: str) -> bool:
    lowered = href.lower()
    return (
        not href
        or href.startswith("#")
        or lowered.startswith("http://")
        or lowered.startswith("https://")
        or lowered.startswith("mailto:")
        or lowered.startswith("tel:")
        or href.startswith("//")
    )


def resolve_local_href(page: Path, href: str) -> Path | None:
    """Resolve a local href to a file, treating directories as index pages."""

    parts = urlsplit(href)
    if parts.scheme:
        return None

    link_path = unquote(parts.path)
    candidate = ROOT / link_path.lstrip("/") if link_path.startswith("/") else page.parent / link_path
    resolved = candidate.resolve()

    try:
        resolved.relative_to(ROOT)
    except ValueError:
        return None

    if resolved.is_dir():
        return resolved / "index.html"
    return resolved


def validate_html_page(page: Path, totals: ValidationTotals) -> list[str]:
    errors: list[str] = []
    parser = PageParser()
    parser.feed(page.read_text(encoding="utf-8"))
    parser.close()
    page_name = display_path(page)

    if parser.html_lang not in {"ja", "ja-JP"}:
        errors.append(f"{page_name}: html lang must be 'ja' or 'ja-JP'.")

    if not "".join(parser.title_parts).strip():
        errors.append(f"{page_name}: missing or empty <title>.")

    if not any(description and description.strip() for description in parser.descriptions):
        errors.append(f"{page_name}: missing or empty meta description.")

    if not any(canonical and canonical.strip() for canonical in parser.canonicals):
        errors.append(f"{page_name}: missing or empty canonical link.")

    for index, json_ld in enumerate(parser.json_ld_blocks, start=1):
        totals.json_ld_blocks += 1
        try:
            json.loads(json_ld)
        except json.JSONDecodeError as error:
            errors.append(f"{page_name}: JSON-LD block {index} is invalid JSON ({error.msg}).")

    for href, line, tag in parser.hrefs:
        if is_ignored_href(href):
            continue

        totals.internal_links += 1
        target = resolve_local_href(page, href)
        if target is None:
            errors.append(f"{page_name}:{line}: <{tag}> href '{href}' uses an unsupported local path.")
        elif not target.exists():
            errors.append(f"{page_name}:{line}: <{tag}> href '{href}' does not exist locally.")

    totals.html_pages += 1
    return errors


def sitemap_target(loc: str) -> Path | None:
    """Map a sitemap URL below BASE_URL to its local HTML page."""

    if not loc.startswith(BASE_URL):
        return None

    path = unquote(urlsplit(loc).path)
    base_path = urlsplit(BASE_URL).path
    relative_path = path.removeprefix(base_path).lstrip("/")
    candidate = (ROOT / relative_path).resolve()

    try:
        candidate.relative_to(ROOT)
    except ValueError:
        return None

    if not relative_path or loc.endswith("/"):
        return candidate / "index.html"
    if candidate.suffix:
        return candidate
    return candidate / "index.html"


def page_url(page: Path) -> str:
    relative_path = page.relative_to(ROOT)
    if relative_path == Path("index.html"):
        return BASE_URL
    return f"{BASE_URL}{relative_path.parent.as_posix()}/"


def validate_sitemap(pages: list[Path], totals: ValidationTotals) -> list[str]:
    errors: list[str] = []
    sitemap = ROOT / "sitemap.xml"

    try:
        root = ElementTree.parse(sitemap).getroot()
    except ElementTree.ParseError as error:
        return [f"sitemap.xml: invalid XML ({error})."]

    locs = [element.text.strip() for element in root.iter() if element.tag.rsplit("}", 1)[-1] == "loc" and element.text]
    totals.sitemap_urls = len(locs)
    seen: set[str] = set()

    for loc in locs:
        if loc in seen:
            errors.append(f"sitemap.xml: duplicate <loc> '{loc}'.")
        seen.add(loc)

        target = sitemap_target(loc)
        if target is None:
            errors.append(f"sitemap.xml: <loc> '{loc}' is outside the site base URL or has an invalid path.")
        elif not target.is_file():
            errors.append(f"sitemap.xml: <loc> '{loc}' has no local HTML page at '{display_path(target)}'.")

    for page in pages:
        expected_url = page_url(page)
        if expected_url not in seen:
            errors.append(f"sitemap.xml: missing public page '{display_path(page)}' ({expected_url}).")

    return errors


def main() -> int:
    totals = ValidationTotals()
    pages = public_pages()
    errors: list[str] = []

    for page in pages:
        errors.extend(validate_html_page(page, totals))

    errors.extend(validate_sitemap(pages, totals))

    if errors:
        print("Site validation failed:", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1

    print(
        "Site validation passed: "
        f"{totals.html_pages} HTML pages, "
        f"{totals.json_ld_blocks} JSON-LD blocks, "
        f"{totals.internal_links} internal links, "
        f"{totals.sitemap_urls} sitemap URLs."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
