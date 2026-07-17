#!/usr/bin/env python3
"""Validate the static pages and crawl files used by Vekpal Football."""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import quote, unquote, urlsplit
from xml.etree import ElementTree


ROOT = Path(__file__).resolve().parents[1]
BASE_URL = "https://vekpal.com/"
GA_SCRIPT_BASE = "https://www.googletagmanager.com/gtag/js"
GA_MEASUREMENT_ID = "G-MJFETE4J77"
GA_SCRIPT_SRC = f"{GA_SCRIPT_BASE}?id={GA_MEASUREMENT_ID}"
ADSENSE_SCRIPT_BASE = "https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js"
ADSENSE_CLIENT_ID = "ca-pub-6151638978197241"
ADSENSE_SCRIPT_SRC = f"{ADSENSE_SCRIPT_BASE}?client={ADSENSE_CLIENT_ID}"
ADS_TXT_RECORD = "google.com, pub-6151638978197241, DIRECT, f08c47fec0942fa0"
SEARCH_CONSOLE_TOKEN = "rP4ZlqpgXEt-Qd5diwi7s-ljC5pc6Ggj6eKVN1sklyY"
EXPECTED_PUBLIC_PAGE_COUNT = 18
EXPECTED_ARTICLE_COUNT = 12
EDITORIAL_POLICY_PAGE = ROOT / "editorial-policy" / "index.html"
CONTACT_PAGE = ROOT / "contact" / "index.html"
CONTACT_URL = "https://vekpal.com/contact/"
CONTACT_EMAIL = "vekpal.contact@gmail.com"
CONTACT_SUBJECT = "Vekpal Footballへのお問い合わせ"
CONTACT_MAILTO = f"mailto:{CONTACT_EMAIL}?subject={quote(CONTACT_SUBJECT)}"
REQUIRED_SVGS = (
    ROOT / "assets" / "offside-position-diagram.svg",
    ROOT / "assets" / "football-positions-diagram.svg",
    ROOT / "assets" / "football-formations-diagram.svg",
)
INDEX_BANNED_PHRASES = (
    "ポートフォリオ用",
    "今後整備予定",
    "将来は日程API",
    "外部APIなし",
    "記事へ展開",
    "記事化しやすい",
    "SEO向け",
    "ロングテール記事向け",
    "Analytics、広告による個人データ収集は行っていません",
)


@dataclass
class ValidationTotals:
    html_pages: int = 0
    json_ld_blocks: int = 0
    internal_links: int = 0
    sitemap_urls: int = 0
    ga4_scripts: int = 0
    adsense_scripts: int = 0
    article_pages: int = 0


class PageParser(HTMLParser):
    """Collect the small set of HTML details needed for static validation."""

    def __init__(self) -> None:
        super().__init__()
        self.html_lang: str | None = None
        self.title_parts: list[str] = []
        self.in_title = False
        self.descriptions: list[str | None] = []
        self.meta_tags: list[dict[str, str | None]] = []
        self.canonicals: list[str | None] = []
        self.hrefs: list[tuple[str, int, str]] = []
        self.json_ld_blocks: list[str] = []
        self.current_json_ld: list[str] | None = None
        self.inline_scripts: list[str] = []
        self.current_inline_script: list[str] | None = None
        self.ga4_scripts: list[dict[str, str | None]] = []
        self.adsense_scripts: list[dict[str, str | None]] = []
        self.search_console_tokens: list[str | None] = []
        self.srcs: list[tuple[str, int, str]] = []
        self.ids: set[str] = set()
        self.footer_hrefs: list[tuple[str, int, str]] = []
        self.in_footer = False
        self.in_script = False
        self.in_style = False
        self.visible_text_parts: list[str] = []
        self.class_elements: list[tuple[str, set[str], dict[str, str | None], int]] = []
        self.article_published_times: list[str | None] = []
        self.article_modified_times: list[str | None] = []
        self.article_meta_depth = 0
        self.article_meta_hrefs: list[str] = []
        self.element_text: dict[str, list[str]] = {
            "countdown-label": [],
            "countdown-days": [],
            "countdown-detail": [],
        }
        self.text_capture_stack: list[tuple[str, str]] = []
        self.tag_counts: dict[str, int] = {}

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = dict(attrs)
        classes = set((attributes.get("class") or "").split())
        self.class_elements.append((tag, classes, attributes, self.getpos()[0]))
        self.tag_counts[tag] = self.tag_counts.get(tag, 0) + 1

        element_id = attributes.get("id")
        if element_id:
            self.ids.add(element_id)
            if element_id in self.element_text:
                self.text_capture_stack.append((tag, element_id))

        entering_article_meta = tag == "dl" and "article-meta" in classes
        if self.article_meta_depth:
            self.article_meta_depth += 1
        elif entering_article_meta:
            self.article_meta_depth = 1

        if tag == "footer":
            self.in_footer = True
        elif tag == "style":
            self.in_style = True

        if tag == "html":
            self.html_lang = attributes.get("lang")
        elif tag == "title":
            self.in_title = True
        elif tag == "meta":
            self.meta_tags.append(attributes)
            meta_name = attributes.get("name", "").lower()
            if meta_name == "description":
                self.descriptions.append(attributes.get("content"))
            elif meta_name == "google-site-verification":
                self.search_console_tokens.append(attributes.get("content"))
        elif tag == "link":
            rel_values = attributes.get("rel", "").lower().split()
            if "canonical" in rel_values:
                self.canonicals.append(attributes.get("href"))
        elif tag == "script":
            self.in_script = True
            script_type = attributes.get("type", "").lower()
            script_src = attributes.get("src")
            if script_type == "application/ld+json":
                self.current_json_ld = []
            elif script_src is None:
                self.current_inline_script = []
            if script_src and script_src.startswith(GA_SCRIPT_BASE):
                self.ga4_scripts.append(attributes)
            if script_src and script_src.startswith(ADSENSE_SCRIPT_BASE):
                self.adsense_scripts.append(attributes)

        if tag == "time" and "article-published" in classes:
            self.article_published_times.append(attributes.get("datetime"))
        if tag == "time" and "article-modified" in classes:
            self.article_modified_times.append(attributes.get("datetime"))

        href = attributes.get("href")
        if href is not None:
            self.hrefs.append((href, self.getpos()[0], tag))
            if self.in_footer:
                self.footer_hrefs.append((href, self.getpos()[0], tag))
            if self.article_meta_depth:
                self.article_meta_hrefs.append(href)

        src = attributes.get("src")
        if src is not None:
            self.srcs.append((src, self.getpos()[0], tag))

    def handle_endtag(self, tag: str) -> None:
        if tag == "title":
            self.in_title = False
        elif tag == "script":
            if self.current_json_ld is not None:
                self.json_ld_blocks.append("".join(self.current_json_ld))
                self.current_json_ld = None
            elif self.current_inline_script is not None:
                self.inline_scripts.append("".join(self.current_inline_script))
                self.current_inline_script = None
            self.in_script = False

        if self.article_meta_depth:
            self.article_meta_depth -= 1
        if tag == "footer":
            self.in_footer = False
        elif tag == "style":
            self.in_style = False

        if self.text_capture_stack and self.text_capture_stack[-1][0] == tag:
            self.text_capture_stack.pop()

    def handle_data(self, data: str) -> None:
        if self.in_title:
            self.title_parts.append(data)
        if self.current_json_ld is not None:
            self.current_json_ld.append(data)
        if self.current_inline_script is not None:
            self.current_inline_script.append(data)
        if not self.in_script and not self.in_style:
            self.visible_text_parts.append(data)
        if self.text_capture_stack:
            self.element_text[self.text_capture_stack[-1][1]].append(data)


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

    expected_canonical = page_url(page)
    if parser.canonicals != [expected_canonical]:
        errors.append(
            f"{page_name}: expected one canonical '{expected_canonical}', found {parser.canonicals}."
        )

    if page == ROOT / "index.html" and parser.search_console_tokens != [SEARCH_CONSOLE_TOKEN]:
        errors.append(f"{page_name}: Search Console verification meta tag changed or is missing.")

    totals.ga4_scripts += len(parser.ga4_scripts)
    if len(parser.ga4_scripts) != 1:
        errors.append(f"{page_name}: expected exactly one GA4 loader script, found {len(parser.ga4_scripts)}.")
    else:
        ga4_script = parser.ga4_scripts[0]
        if ga4_script.get("src") != GA_SCRIPT_SRC:
            errors.append(f"{page_name}: GA4 script src must use measurement ID '{GA_MEASUREMENT_ID}'.")
        if "async" not in ga4_script:
            errors.append(f"{page_name}: GA4 loader script must include the async attribute.")

    ga4_config = f'gtag("config", "{GA_MEASUREMENT_ID}")'
    ga4_config_count = sum(script.count(ga4_config) for script in parser.inline_scripts)
    if ga4_config_count != 1:
        errors.append(f"{page_name}: expected exactly one GA4 config call, found {ga4_config_count}.")

    totals.adsense_scripts += len(parser.adsense_scripts)
    if len(parser.adsense_scripts) != 1:
        errors.append(f"{page_name}: expected exactly one Google AdSense script, found {len(parser.adsense_scripts)}.")
    else:
        adsense_script = parser.adsense_scripts[0]
        if adsense_script.get("src") != ADSENSE_SCRIPT_SRC:
            errors.append(
                f"{page_name}: AdSense script src must use client ID '{ADSENSE_CLIENT_ID}'."
            )
        if "async" not in adsense_script:
            errors.append(f"{page_name}: AdSense script must include the async attribute.")
        if adsense_script.get("crossorigin") != "anonymous":
            errors.append(f"{page_name}: AdSense script crossorigin must be 'anonymous'.")

    parsed_json_ld: list[object] = []
    for index, json_ld in enumerate(parser.json_ld_blocks, start=1):
        totals.json_ld_blocks += 1
        try:
            parsed_json_ld.append(json.loads(json_ld))
        except json.JSONDecodeError as error:
            errors.append(f"{page_name}: JSON-LD block {index} is invalid JSON ({error.msg}).")

    article_records = [
        record
        for record in parsed_json_ld
        if isinstance(record, dict) and record.get("@type") == "Article"
    ]
    if article_records:
        totals.article_pages += 1
        if len(article_records) != 1:
            errors.append(f"{page_name}: expected one Article JSON-LD block, found {len(article_records)}.")
        article = article_records[0]
        published = article.get("datePublished")
        modified = article.get("dateModified")

        article_meta_count = sum(
            1
            for tag, classes, _attributes, _line in parser.class_elements
            if tag == "dl" and "article-meta" in classes
        )
        if article_meta_count != 1:
            errors.append(f"{page_name}: expected one visible article metadata block, found {article_meta_count}.")
        if parser.article_published_times != [published]:
            errors.append(
                f"{page_name}: displayed publication date {parser.article_published_times} "
                f"does not match JSON-LD datePublished '{published}'."
            )
        if parser.article_modified_times != [modified]:
            errors.append(
                f"{page_name}: displayed update date {parser.article_modified_times} "
                f"does not match JSON-LD dateModified '{modified}'."
            )
        metadata_editorial_links = [
            href
            for href in parser.article_meta_hrefs
            if resolve_local_href(page, href) == EDITORIAL_POLICY_PAGE
        ]
        if len(metadata_editorial_links) != 1:
            errors.append(f"{page_name}: article metadata must link once to Editorial Policy.")
        visible_text = " ".join(parser.visible_text_parts)
        if "Vekpal Football" not in visible_text:
            errors.append(f"{page_name}: article metadata is missing the operator name Vekpal Football.")

    footer_editorial_links = [
        href
        for href, _line, _tag in parser.footer_hrefs
        if resolve_local_href(page, href) == EDITORIAL_POLICY_PAGE
    ]
    if len(footer_editorial_links) != 1:
        errors.append(f"{page_name}: footer must contain exactly one Editorial Policy link.")

    footer_contact_links = [
        href
        for href, _line, _tag in parser.footer_hrefs
        if resolve_local_href(page, href) == CONTACT_PAGE
    ]
    if len(footer_contact_links) != 1:
        errors.append(f"{page_name}: footer must contain exactly one Contact link.")

    for href, line, tag in parser.hrefs:
        if href.startswith("#"):
            fragment = unquote(urlsplit(href).fragment)
            if fragment and fragment not in parser.ids:
                errors.append(f"{page_name}:{line}: <{tag}> fragment '#{fragment}' has no matching id.")
            continue
        if is_ignored_href(href):
            continue

        totals.internal_links += 1
        target = resolve_local_href(page, href)
        if target is None:
            errors.append(f"{page_name}:{line}: <{tag}> href '{href}' uses an unsupported local path.")
        elif not target.exists():
            errors.append(f"{page_name}:{line}: <{tag}> href '{href}' does not exist locally.")

    for src, line, tag in parser.srcs:
        if is_ignored_href(src):
            continue
        target = resolve_local_href(page, src)
        if target is None:
            errors.append(f"{page_name}:{line}: <{tag}> src '{src}' uses an unsupported local path.")
        elif not target.exists():
            errors.append(f"{page_name}:{line}: <{tag}> src '{src}' does not exist locally.")

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


def parse_page(page: Path) -> PageParser:
    parser = PageParser()
    parser.feed(page.read_text(encoding="utf-8"))
    parser.close()
    return parser


def meta_values(parser: PageParser, attribute: str, key: str) -> list[str | None]:
    """Return content values for matching named or property metadata."""

    return [
        attributes.get("content")
        for attributes in parser.meta_tags
        if attributes.get(attribute, "").lower() == key.lower()
    ]


def validate_index_page() -> list[str]:
    errors: list[str] = []
    page = ROOT / "index.html"
    parser = parse_page(page)
    visible_text = " ".join(parser.visible_text_parts)

    for phrase in INDEX_BANNED_PHRASES:
        if phrase in visible_text:
            errors.append(f"index.html: banned unfinished phrase remains: '{phrase}'.")

    countdown_text = {
        element_id: "".join(parts).strip()
        for element_id, parts in parser.element_text.items()
    }
    if countdown_text["countdown-days"] in {"", "--"}:
        errors.append("index.html: countdown must have meaningful initial HTML instead of '--'.")
    if not countdown_text["countdown-label"] or not countdown_text["countdown-detail"]:
        errors.append("index.html: countdown fallback label and detail must be present.")

    card_requirements = {
        "article-card": (12, 12),
        "guide-card": (3, 6),
        "topic-card": (1, 6),
        "info-card": (3, 3),
    }
    for card_class, (minimum, maximum) in card_requirements.items():
        cards = [
            (tag, attributes, line)
            for tag, classes, attributes, line in parser.class_elements
            if card_class in classes
        ]
        if not minimum <= len(cards) <= maximum:
            errors.append(
                f"index.html: expected {minimum}-{maximum} '.{card_class}' elements, found {len(cards)}."
            )
        for tag, attributes, line in cards:
            if tag != "a" or not attributes.get("href"):
                errors.append(
                    f"index.html:{line}: '.{card_class}' must be a full linked <a> card."
                )

    article_cards = [
        attributes
        for tag, classes, attributes, _line in parser.class_elements
        if tag == "a" and "article-card" in classes
    ]
    article_hrefs = [attributes.get("href") for attributes in article_cards]
    if len(set(article_hrefs)) != len(article_hrefs):
        errors.append("index.html: article-card links must be unique.")
    for attributes in article_cards:
        if not attributes.get("data-category") or not attributes.get("data-keywords"):
            errors.append("index.html: every article-card needs data-category and data-keywords.")

    deleted_section_ids = {
        "match-center",
        "competitions",
        "team-finder",
        "spotlight",
        "clubs",
        "history",
    }
    unexpected_ids = deleted_section_ids.intersection(parser.ids)
    if unexpected_ids:
        errors.append(f"index.html: removed placeholder sections remain: {sorted(unexpected_ids)}.")

    countdown_scripts = [src for src, _line, _tag in parser.srcs if src == "countdown.js"]
    if len(countdown_scripts) != 1:
        errors.append("index.html: countdown.js must be loaded exactly once.")

    return errors


def validate_contact_page() -> list[str]:
    errors: list[str] = []
    if not CONTACT_PAGE.is_file():
        return ["contact/index.html: contact page is missing."]

    parser = parse_page(CONTACT_PAGE)
    page_name = display_path(CONTACT_PAGE)
    content = CONTACT_PAGE.read_text(encoding="utf-8")

    if parser.canonicals != [CONTACT_URL]:
        errors.append(f"{page_name}: canonical must be exactly '{CONTACT_URL}'.")
    if parser.search_console_tokens != [SEARCH_CONSOLE_TOKEN]:
        errors.append(f"{page_name}: Search Console verification meta tag changed or is missing.")

    expected_meta = {
        ("property", "og:type"): "website",
        ("property", "og:site_name"): "Vekpal Football",
        ("property", "og:title"): "お問い合わせ｜Vekpal Football",
        ("property", "og:url"): CONTACT_URL,
        ("property", "og:image"): f"{BASE_URL}assets/hero-stadium.png",
        ("property", "og:locale"): "ja_JP",
        ("name", "twitter:card"): "summary_large_image",
        ("name", "twitter:title"): "お問い合わせ｜Vekpal Football",
        ("name", "twitter:image"): f"{BASE_URL}assets/hero-stadium.png",
    }
    for (attribute, key), expected in expected_meta.items():
        values = meta_values(parser, attribute, key)
        if values != [expected]:
            errors.append(f"{page_name}: expected one {key} meta value '{expected}', found {values}.")

    for attribute, key in (
        ("property", "og:description"),
        ("property", "og:image:alt"),
        ("name", "twitter:description"),
        ("name", "twitter:image:alt"),
    ):
        values = meta_values(parser, attribute, key)
        if len(values) != 1 or not values[0] or not values[0].strip():
            errors.append(f"{page_name}: expected one non-empty {key} meta value.")

    if len(parser.json_ld_blocks) != 1:
        errors.append(f"{page_name}: expected exactly one JSON-LD block, found {len(parser.json_ld_blocks)}.")
    else:
        try:
            webpage = json.loads(parser.json_ld_blocks[0])
        except json.JSONDecodeError:
            webpage = None
        if not isinstance(webpage, dict) or webpage.get("@type") != "WebPage":
            errors.append(f"{page_name}: the JSON-LD block must describe one WebPage.")
        else:
            expected_webpage_fields = {
                "url": CONTACT_URL,
                "mainEntityOfPage": CONTACT_URL,
                "inLanguage": "ja-JP",
            }
            for key, expected in expected_webpage_fields.items():
                if webpage.get(key) != expected:
                    errors.append(f"{page_name}: WebPage {key} must be '{expected}'.")
            publisher = webpage.get("publisher")
            if not isinstance(publisher, dict) or publisher.get("name") != "Vekpal Football":
                errors.append(f"{page_name}: WebPage publisher must be Vekpal Football.")

    ga4_sources = [attributes.get("src") for attributes in parser.ga4_scripts]
    if ga4_sources != [GA_SCRIPT_SRC]:
        errors.append(f"{page_name}: contact page must retain the exact GA4 loader.")
    adsense_sources = [attributes.get("src") for attributes in parser.adsense_scripts]
    if adsense_sources != [ADSENSE_SCRIPT_SRC]:
        errors.append(f"{page_name}: contact page must retain the exact AdSense loader.")

    hrefs = [href for href, _line, _tag in parser.hrefs]
    if hrefs.count(CONTACT_MAILTO) != 1:
        errors.append(f"{page_name}: expected one mailto link with the required subject.")
    if not is_ignored_href(CONTACT_MAILTO) or resolve_local_href(CONTACT_PAGE, CONTACT_MAILTO) is not None:
        errors.append(f"{page_name}: mailto links must not be treated as local files.")

    visible_text = " ".join(parser.visible_text_parts)
    if visible_text.count(CONTACT_EMAIL) != 1 or content.count(CONTACT_EMAIL) != 2:
        errors.append(f"{page_name}: contact email must appear once visibly and once in its mailto link.")

    required_text = (
        "一般的なお問い合わせ",
        "記事内容の訂正依頼",
        "著作権・権利関係",
        "広告・掲載に関するお問い合わせ",
        "返信を保証するものではありません",
        "営業・勧誘などの内容によっては返信しない場合があります",
        "パスワード",
        "住所",
        "電話番号",
        "決済情報",
        "機密情報",
        "お問い合わせフォームは設置していません",
    )
    for text in required_text:
        if text not in visible_text:
            errors.append(f"{page_name}: required contact guidance is missing: '{text}'.")

    if parser.tag_counts.get("form", 0):
        errors.append(f"{page_name}: an inquiry form must not be implemented.")

    required_footer_targets = {
        "top page": ROOT / "index.html",
        "About": ROOT / "about" / "index.html",
        "Privacy Policy": ROOT / "privacy-policy" / "index.html",
        "Editorial Policy": EDITORIAL_POLICY_PAGE,
        "All Guides": ROOT / "guides" / "index.html",
    }
    for label, target in required_footer_targets.items():
        matches = [
            href
            for href, _line, _tag in parser.footer_hrefs
            if resolve_local_href(CONTACT_PAGE, href) == target
        ]
        if len(matches) != 1:
            errors.append(f"{page_name}: footer must link exactly once to {label}.")

    return errors


def validate_contact_email_location() -> list[str]:
    """Prevent the public contact address from leaking into unrelated files."""

    allowed = {CONTACT_PAGE.resolve(), Path(__file__).resolve()}
    email_bytes = CONTACT_EMAIL.encode("utf-8")
    matches: list[Path] = []

    for path in ROOT.rglob("*"):
        if not path.is_file() or ".git" in path.parts or "__pycache__" in path.parts:
            continue
        if email_bytes in path.read_bytes():
            matches.append(path.resolve())

    unexpected = sorted(path for path in matches if path not in allowed)
    if unexpected:
        names = ", ".join(display_path(path) for path in unexpected)
        return [f"contact email appears in unexpected files: {names}."]
    if CONTACT_PAGE.resolve() not in matches:
        return ["contact/index.html: expected contact email is missing."]
    return []


def validate_privacy_contact_disclosure() -> list[str]:
    page = ROOT / "privacy-policy" / "index.html"
    content = page.read_text(encoding="utf-8")
    required_text = (
        "送信元のメールアドレス",
        "氏名またはハンドルネーム",
        "お問い合わせ本文",
        "お問い合わせへの返信",
        "本人確認",
        "記事内容の訂正対応",
        "権利関係の確認",
        "目的を超えて利用したり、不必要に第三者へ提供したりすることはありません",
        "必要と考えられる期間に限って、適切な方法で管理するよう努めます",
    )
    return [
        f"privacy-policy/index.html: contact disclosure is missing: '{text}'."
        for text in required_text
        if text not in content
    ]


def validate_schedule_page() -> list[str]:
    page = ROOT / "world-cup-2026-schedule" / "index.html"
    content = page.read_text(encoding="utf-8")
    required_text = (
        "大会全体",
        "グループステージ第1節",
        "グループステージ第2節",
        "グループステージ第3節",
        "ラウンド32",
        "ラウンド16",
        "準々決勝",
        "準決勝",
        "3位決定戦",
        "決勝",
        "最終確認はFIFA公式",
        "最終確認日: 2026年7月16日",
    )
    return [
        f"world-cup-2026-schedule/index.html: required schedule text is missing: '{text}'."
        for text in required_text
        if text not in content
    ]


def validate_article_figures() -> list[str]:
    errors: list[str] = []
    expected = {
        ROOT / "offside-rule-guide" / "index.html": "../assets/offside-position-diagram.svg",
        ROOT / "football-positions-guide" / "index.html": "../assets/football-positions-diagram.svg",
        ROOT / "football-formations-guide" / "index.html": "../assets/football-formations-diagram.svg",
    }

    for page, expected_src in expected.items():
        parser = parse_page(page)
        page_name = display_path(page)
        figures = [
            (tag, attributes)
            for tag, classes, attributes, _line in parser.class_elements
            if tag == "figure" and "article-figure" in classes
        ]
        matching_images = [
            attributes
            for tag, _classes, attributes, _line in parser.class_elements
            if tag == "img" and attributes.get("src") == expected_src
        ]
        if len(figures) != 1 or parser.tag_counts.get("figcaption", 0) < 1:
            errors.append(f"{page_name}: expected one article figure with a figcaption.")
        if len(matching_images) != 1:
            errors.append(f"{page_name}: expected one image using '{expected_src}'.")
        elif not (matching_images[0].get("alt") or "").strip():
            errors.append(f"{page_name}: diagram image needs meaningful alt text.")

    return errors


def validate_svgs() -> list[str]:
    errors: list[str] = []
    for svg in REQUIRED_SVGS:
        name = display_path(svg)
        if not svg.is_file():
            errors.append(f"{name}: required SVG is missing.")
            continue

        raw = svg.read_text(encoding="utf-8")
        try:
            root = ElementTree.fromstring(raw)
        except ElementTree.ParseError as error:
            errors.append(f"{name}: invalid SVG XML ({error}).")
            continue

        if not root.get("viewBox"):
            errors.append(f"{name}: root SVG must include a viewBox.")
        if root.get("width") or root.get("height"):
            errors.append(f"{name}: root SVG must not use fixed width or height attributes.")

        local_tags = [element.tag.rsplit("}", 1)[-1] for element in root.iter()]
        if "title" not in local_tags or "desc" not in local_tags:
            errors.append(f"{name}: SVG must include title and desc elements.")
        if "script" in local_tags:
            errors.append(f"{name}: SVG must not contain scripts.")

        for element in root.iter():
            if element.tag.rsplit("}", 1)[-1] != "image":
                continue
            image_href = next(
                (value for key, value in element.attrib.items() if key.rsplit("}", 1)[-1] == "href"),
                "",
            )
            if image_href.startswith(("http://", "https://", "//", "data:")):
                errors.append(f"{name}: SVG must not load an external or embedded raster image.")

        lowered = raw.lower()
        if "@import" in lowered or "url(http" in lowered or "url(//" in lowered:
            errors.append(f"{name}: SVG must not load external fonts or styles.")

    return errors


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
    expected_urls = {page_url(page) for page in pages}

    if len(locs) != len(pages):
        errors.append(
            f"sitemap.xml: expected one URL for each of {len(pages)} public pages, found {len(locs)}."
        )

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

    for loc in seen - expected_urls:
        errors.append(f"sitemap.xml: URL has no corresponding public page: '{loc}'.")

    contact_entries: list[dict[str, str]] = []
    for element in root.iter():
        if element.tag.rsplit("}", 1)[-1] != "url":
            continue
        entry = {
            child.tag.rsplit("}", 1)[-1]: (child.text or "").strip()
            for child in element
        }
        if entry.get("loc") == CONTACT_URL:
            contact_entries.append(entry)

    if len(contact_entries) != 1:
        errors.append(f"sitemap.xml: expected exactly one Contact URL entry, found {len(contact_entries)}.")
    else:
        expected_contact_entry = {
            "loc": CONTACT_URL,
            "lastmod": "2026-07-17",
            "changefreq": "yearly",
            "priority": "0.5",
        }
        if contact_entries[0] != expected_contact_entry:
            errors.append(
                f"sitemap.xml: Contact entry must be {expected_contact_entry}, found {contact_entries[0]}."
            )

    return errors


def validate_ads_txt() -> list[str]:
    ads_txt = ROOT / "ads.txt"
    if not ads_txt.is_file():
        return ["ads.txt: file is missing from the repository root."]

    expected_content = f"{ADS_TXT_RECORD}\n"
    actual_content = ads_txt.read_text(encoding="utf-8")
    if actual_content != expected_content:
        return ["ads.txt: content must contain exactly the required AdSense record."]

    return []


def main() -> int:
    totals = ValidationTotals()
    pages = public_pages()
    errors: list[str] = []

    if len(pages) != EXPECTED_PUBLIC_PAGE_COUNT:
        errors.append(
            f"site: expected {EXPECTED_PUBLIC_PAGE_COUNT} public HTML pages, found {len(pages)}."
        )

    for page in pages:
        errors.extend(validate_html_page(page, totals))

    if totals.article_pages != EXPECTED_ARTICLE_COUNT:
        errors.append(
            f"site: expected {EXPECTED_ARTICLE_COUNT} Article pages, found {totals.article_pages}."
        )

    errors.extend(validate_index_page())
    errors.extend(validate_contact_page())
    errors.extend(validate_contact_email_location())
    errors.extend(validate_privacy_contact_disclosure())
    errors.extend(validate_schedule_page())
    errors.extend(validate_article_figures())
    errors.extend(validate_svgs())
    errors.extend(validate_sitemap(pages, totals))
    errors.extend(validate_ads_txt())

    if errors:
        print("Site validation failed:", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1

    print(
        "Site validation passed: "
        f"{totals.html_pages} HTML pages, "
        f"{totals.article_pages} articles, "
        f"{totals.ga4_scripts} GA4 scripts, "
        f"{totals.adsense_scripts} AdSense scripts, "
        f"{totals.json_ld_blocks} JSON-LD blocks, "
        f"{totals.internal_links} internal links, "
        f"{totals.sitemap_urls} sitemap URLs."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
