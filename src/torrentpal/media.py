import json
import re
from collections.abc import Callable
from pathlib import Path

from playwright.sync_api import sync_playwright

from torrentpal.domain import Tag


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
    report_status: Callable[[str], None],
) -> tuple[Path, ...]:
    report_status("Loading browser cookies")
    cookies_export = json.loads(cookies_path.read_text(encoding="utf-8"))
    cookies = []
    for exported_cookie in cookies_export:
        cookie = {
            "name": exported_cookie["name"],
            "value": exported_cookie["value"],
            "domain": exported_cookie["domain"],
            "path": exported_cookie["path"],
            "httpOnly": exported_cookie["httpOnly"],
            "secure": exported_cookie["secure"],
        }
        if "expirationDate" in exported_cookie:
            cookie["expires"] = exported_cookie["expirationDate"]
        if exported_cookie["sameSite"] != "unspecified":
            cookie["sameSite"] = {
                "strict": "Strict",
                "lax": "Lax",
                "no_restriction": "None",
            }[exported_cookie["sameSite"]]
        cookies.append(cookie)

    with sync_playwright() as playwright:
        report_status("Starting headless browser")
        browser = playwright.chromium.launch(headless=True)
        context = browser.new_context()
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
        page.goto(page_url)
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
    cookies_export = json.loads(cookies_path.read_text(encoding="utf-8"))
    cookies = []
    for exported_cookie in cookies_export:
        cookie = {
            "name": exported_cookie["name"],
            "value": exported_cookie["value"],
            "domain": exported_cookie["domain"],
            "path": exported_cookie["path"],
            "httpOnly": exported_cookie["httpOnly"],
            "secure": exported_cookie["secure"],
        }
        if "expirationDate" in exported_cookie:
            cookie["expires"] = exported_cookie["expirationDate"]
        if exported_cookie["sameSite"] != "unspecified":
            cookie["sameSite"] = {
                "strict": "Strict",
                "lax": "Lax",
                "no_restriction": "None",
            }[exported_cookie["sameSite"]]
        cookies.append(cookie)

    with sync_playwright() as playwright:
        report_status("Starting headless browser")
        browser = playwright.chromium.launch(headless=True)
        context = browser.new_context()
        context.add_cookies(cookies)
        page = context.new_page()
        report_status(f"Opening comment link: {page_url}")
        page.goto(page_url)
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
