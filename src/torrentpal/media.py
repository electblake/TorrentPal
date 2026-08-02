import json
import re
from collections.abc import Callable
from json import JSONDecodeError
from pathlib import Path

from playwright.sync_api import sync_playwright

from torrentpal.domain import Tag


class CookieConfigurationError(ValueError):
    """Raised when a browser cookie export cannot be parsed."""


def parse_browser_cookies(contents: str) -> list[dict[str, object]]:
    """Convert a JSON browser-cookie export for Playwright."""
    cookies_export = _validated_cookie_export(contents)
    return [
        _playwright_cookie(exported_cookie, index)
        for index, exported_cookie in enumerate(cookies_export, start=1)
    ]


def format_browser_cookie_json(contents: str) -> str:
    """Validate and format a browser-cookie export as canonical JSON."""
    return json.dumps(_validated_cookie_export(contents), indent=2)


def _validated_cookie_export(contents: str) -> list[object]:
    contents = contents.lstrip("\ufeff")
    if not contents.strip():
        raise CookieConfigurationError("Cookies JSON cannot be empty; use [] for none")
    try:
        cookies_export = json.loads(contents)
    except JSONDecodeError as error:
        raise CookieConfigurationError("Cookies must be valid JSON") from error
    if not isinstance(cookies_export, list):
        raise CookieConfigurationError("A JSON cookies export must contain a list")
    for index, exported_cookie in enumerate(cookies_export, start=1):
        _playwright_cookie(exported_cookie, index)
    return cookies_export


def load_browser_cookies(cookies_path: Path) -> list[dict[str, object]]:
    """Load optional browser cookies from disk without exposing their values."""
    if not cookies_path.exists():
        return []
    return parse_browser_cookies(cookies_path.read_text(encoding="utf-8"))


def _playwright_cookie(exported_cookie: object, index: int) -> dict[str, object]:
    if not isinstance(exported_cookie, dict):
        raise CookieConfigurationError(f"Cookie {index} must be a JSON object")
    required_fields = ("name", "value", "domain", "path")
    missing_fields = [
        field for field in required_fields if field not in exported_cookie
    ]
    if missing_fields:
        raise CookieConfigurationError(
            f"Cookie {index} is missing required fields: {', '.join(missing_fields)}"
        )

    cookie: dict[str, object] = {
        field: str(exported_cookie[field]) for field in required_fields
    }
    cookie["httpOnly"] = bool(exported_cookie.get("httpOnly", False))
    cookie["secure"] = bool(exported_cookie.get("secure", False))
    expiration = exported_cookie.get("expirationDate")
    if isinstance(expiration, int | float) and expiration > 0:
        cookie["expires"] = float(expiration)
    same_site = str(exported_cookie.get("sameSite", "unspecified")).lower()
    if same_site != "unspecified":
        same_site_value = {
            "strict": "Strict",
            "lax": "Lax",
            "no_restriction": "None",
            "none": "None",
        }.get(same_site)
        if same_site_value is None:
            raise CookieConfigurationError(
                f"Cookie {index} has an unsupported sameSite value"
            )
        cookie["sameSite"] = same_site_value
    return cookie


def first_url(comment: str) -> str:
    return re.search(r"https?://[^\s<>\"']+", comment).group()


def cached_images(
    data_dir: Path,
    torrent_hash: str,
    minimum_width: int,
    minimum_height: int,
    maximum_images: int,
) -> tuple[Path, ...]:
    def dimensions(path: Path) -> tuple[int, int, int]:
        match = re.search(r"_(\d+)x(\d+)_\d+$", path.name)
        width, height = int(match.group(1)), int(match.group(2))
        return width * height, width, height

    paths = (
        path
        for path in data_dir.glob(f"{torrent_hash}_*x*_*")
        if dimensions(path)[1] >= minimum_width
        and dimensions(path)[2] >= minimum_height
    )
    return tuple(sorted(paths, key=dimensions, reverse=True)[:maximum_images])


def download_images(
    page_url: str,
    cookies_path: Path,
    data_dir: Path,
    torrent_hash: str,
    minimum_width: int,
    minimum_height: int,
    maximum_images: int,
    click_all_hidden_contents: bool,
    report_status: Callable[[str], None],
) -> tuple[Path, ...]:
    report_status("Loading browser cookies")
    cookies = load_browser_cookies(cookies_path)
    report_status(f"Loaded {len(cookies)} browser cookies")

    with sync_playwright() as playwright:
        report_status("Starting headless browser")
        browser = playwright.chromium.launch(headless=True)
        context = browser.new_context()
        if cookies:
            context.add_cookies(cookies)
        page = context.new_page()
        responses = {}

        def record_response(response):
            request = response.request
            while request.redirected_from is not None:
                request = request.redirected_from
            responses[request.url] = response
            responses[response.url] = response
            if response.status >= 400:
                report_status(f"HTTP {response.status}: {response.url}")

        page.on("response", record_response)
        page.on(
            "requestfailed",
            lambda request: report_status(
                f"Request failed: {request.failure} ({request.url})"
            ),
        )
        report_status(f"Opening comment link: {page_url}")
        page.goto(page_url, wait_until="domcontentloaded")
        if click_all_hidden_contents:
            report_status("Revealing hidden content")
            show_links = page.get_by_role("link", name="Show", exact=True)
            revealed_sections = 0
            while show_links.count():
                links_before_click = show_links.count()
                show_links.first.click()
                revealed_sections += 1
                if revealed_sections > 1000:
                    raise RuntimeError("Too many hidden content sections to reveal")
                if show_links.count() >= links_before_click:
                    raise RuntimeError("A Show link did not reveal its hidden content")
            report_status(f"Revealed {revealed_sections} hidden content sections")
        report_status("Selecting qualifying images")
        images = page.locator("img").evaluate_all(
            """(images, settings) => [...new Map(images.map(image => ({
                url: image.currentSrc,
                width: image.naturalWidth,
                height: image.naturalHeight
            })).map(image => [image.url, image])).values()]
                .filter(image => image.width >= settings.minimumWidth &&
                    image.height >= settings.minimumHeight)
                .sort((left, right) =>
                    right.width * right.height - left.width * left.height)
                .slice(0, settings.maximumImages)""",
            {
                "minimumWidth": minimum_width,
                "minimumHeight": minimum_height,
                "maximumImages": maximum_images,
            },
        )
        report_status(f"Caching {len(images)} images")
        data_dir.mkdir(parents=True, exist_ok=True)
        for image_path in data_dir.glob(f"{torrent_hash}_*x*_*"):
            image_path.unlink()
        for index, image in enumerate(images):
            destination = (
                data_dir / f"{torrent_hash}_{image['width']}x{image['height']}_{index}"
            )
            destination.write_bytes(responses[image["url"]].body())
        browser.close()
        report_status("Headless browser closed")
    return cached_images(
        data_dir,
        torrent_hash,
        minimum_width,
        minimum_height,
        maximum_images,
    )


def download_tags(
    page_url: str,
    cookies_path: Path,
    selectors: tuple[str, ...],
    minimum_link_text_length: int,
    name_excludes: tuple[str, ...],
    report_status: Callable[[str], None],
) -> tuple[Tag, ...]:
    report_status("Loading browser cookies")
    cookies = load_browser_cookies(cookies_path)
    report_status(f"Loaded {len(cookies)} browser cookies")

    with sync_playwright() as playwright:
        report_status("Starting headless browser")
        browser = playwright.chromium.launch(headless=True)
        context = browser.new_context()
        if cookies:
            context.add_cookies(cookies)
        page = context.new_page()
        report_status(f"Opening comment link: {page_url}")
        page.goto(page_url, wait_until="domcontentloaded")
        report_status("Selecting qualifying tags")
        links = page.locator(", ".join(f"{selector} a" for selector in selectors))
        candidates = links.evaluate_all(
            """links => links.map(link => ({
                name: link.textContent.trim(),
                url: link.href
            }))"""
        )
        tags = tuple(
            Tag(candidate["name"], candidate["url"])
            for candidate in candidates
            if len(re.sub("[^a-z]", "", candidate["name"], flags=re.IGNORECASE))
            >= minimum_link_text_length
            and not any(
                re.search(pattern, candidate["name"]) for pattern in name_excludes
            )
        )
        browser.close()
        report_status("Headless browser closed")
    return tags
