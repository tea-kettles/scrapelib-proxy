"""Utility functions for handling proxies, HTTP methods, and HTML parsing in web scraping."""

import random
from enum import Enum
import logging
import json
import re
import contextlib
from typing import Dict
from urllib.parse import urlparse
import aiohttp
from aiohttp_socks import ProxyConnector
import lxml.html
from tqdm import tqdm

logger = logging.getLogger(__name__)


class HTTPMethod(Enum):
    """Enumeration of HTTP methods."""

    GET = "GET"
    HEAD = "HEAD"
    POST = "POST"
    PUT = "PUT"
    DELETE = "DELETE"


class ProxyType(Enum):
    """Enumeration of proxy types."""

    HTTP = "HTTP"
    SOCKS = "SOCKS"


def get_exponential_backoff(attempt, base_delay=1.0, jitter=True, max_delay=60.0):
    """Calculate an exponential backoff delay with optional jitter."""
    delay = base_delay * (2**attempt)
    if jitter:
        delay += random.uniform(0.2, 0.5)
    return min(delay, max_delay)


async def validate_proxy(
    proxy: str,
    proxy_type: ProxyType,
    url="https://api.ipify.org?format=json",
    timeout: int = 5,
) -> bool:
    """Validate a proxy by making a GET request to a test URL."""
    test_url = url

    # Ensure the proxy URL is properly formatted
    try:
        if proxy_type == ProxyType.SOCKS:
            connector = ProxyConnector.from_url(proxy, ssl=False)
        else:
            connector = aiohttp.TCPConnector(force_close=True, ssl=False)

        # Create a session with the specified proxy
        async with aiohttp.ClientSession(connector=connector) as session:
            async with session.get(
                test_url, proxy=proxy, timeout=aiohttp.ClientTimeout(total=timeout)
            ) as resp:
                logger.debug(
                    "Proxy %s (%s) status: %s", proxy, proxy_type.name, resp.status
                )
            return resp.status == 200

    except (
        aiohttp.ClientConnectionError,
        aiohttp.ClientResponseError,
        aiohttp.ClientPayloadError,
        aiohttp.ClientError,
    ) as e:
        logger.debug(
            "Proxy failed: %s (%s) - %s: %s",
            proxy,
            proxy_type.name,
            type(e).__name__,
            e,
        )
        return False


def parse_html_for_license(html):
    """
    Parses HTML for license/copyright/attribution info.
    Returns a dict of all relevant metadata, regex matches, and JSON-LD licenses.
    """
    # 1. Raw HTML parsing for <meta> tags
    doc = lxml.html.fromstring(html)
    meta_license = {}
    for meta in doc.xpath("//meta"):
        name = meta.attrib.get("name", "").lower()
        content = meta.attrib.get("content", "")
        if any(
            word in name for word in ["license", "copyright", "rights", "attribution"]
        ):
            meta_license[name] = content

    # 2. Regex hunt for license/copyright in HTML text
    regex_licenses = re.findall(
        r"license.{0,50}?(https?://\S+|cc\s*by|creative\s*commons)", html, re.I
    )

    # 3. Try parsing schema.org or json-ld for license keys
    licenses_jsonld = []
    for script in doc.xpath('//script[@type="application/ld+json"]'):
        try:
            data = json.loads(script.text)
            if isinstance(data, dict) and "license" in data:
                licenses_jsonld.append(data["license"])
            elif isinstance(data, list):
                for entry in data:
                    if isinstance(entry, dict) and "license" in entry:
                        licenses_jsonld.append(entry["license"])
        except (OSError, json.JSONDecodeError) as e:
            logger.debug("Error parsing JSON-LD license: %s", e)
            continue

    # Consolidate results
    return {
        "meta": meta_license,
        "regex_matches": regex_licenses,
        "jsonld": licenses_jsonld,
    }


def random_headers() -> Dict[str, str]:
    """Return a random, realistic set of browser HTTP headers."""

    def _chrome_headers(win=True):
        return {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
                if win
                else "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            "Accept": random.choice(
                [
                    "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
                    "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                ]
            ),
            "Accept-Language": random.choice(["en-US,en;q=0.9", "en-GB,en;q=0.8"]),
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
            "Sec-CH-UA": (
                '"Chromium";v="124", "Google Chrome";v="124", "Not.A/Brand";v="99"'
                if win
                else '"Google Chrome";v="124", "Chromium";v="124", "Not=A?Brand";v="24"'
            ),
            "Sec-CH-UA-Mobile": "?0",
            "Sec-CH-UA-Platform": '"Windows"' if win else '"macOS"',
            "Sec-Fetch-Site": "none",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-User": "?1",
            "Sec-Fetch-Dest": "document",
            "Upgrade-Insecure-Requests": "1",
            "DNT": random.choice(["1", "0"]),
        }

    def _firefox_headers(win=True):
        return {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) Gecko/20100101 Firefox/125.0"
                if win
                else "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:125.0) Gecko/20100101 Firefox/125.0"
            ),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": random.choice(["en-US,en;q=0.9", "en-GB,en;q=0.8"]),
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
            "DNT": random.choice(["1", "0"]),
        }

    def _safari_headers():
        return {
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 13_4_1) "
                "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Safari/605.1.15"
            ),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
        }

    # Profiles: (function, args)
    profiles = [
        lambda: _chrome_headers(win=True),
        lambda: _chrome_headers(win=False),
        lambda: _firefox_headers(win=True),
        lambda: _firefox_headers(win=False),
        _safari_headers,
    ]

    headers = random.choice(profiles)()

    # Optionally add Referer or Cache-Control for realism
    referers = [
        "https://www.google.com/",
        "https://www.bing.com/",
        "https://duckduckgo.com/",
        "https://news.ycombinator.com/",
        None,
    ]
    ref = random.choice(referers)
    if ref:
        headers["Referer"] = ref

    cache_control = random.choice(
        ["max-age=0", "no-cache", "no-store", "private", None]
    )
    if cache_control:
        headers["Cache-Control"] = cache_control

    return headers


def sanitize_filename(s):
    """Sanitize a string to be used as a filename."""
    # Replace anything that's not a filename char with '_'
    return re.sub(r'[\\/*?:"<>|]', "_", s)


def infer_type(proxy: str) -> ProxyType:
    """Infer the type of proxy based on URL scheme."""
    scheme = urlparse(proxy.strip()).scheme.lower()
    if scheme in ("http", "https"):
        return ProxyType.HTTP
    elif scheme.startswith("socks"):
        return ProxyType.SOCKS
    raise ValueError(f"Unsupported proxy scheme '{scheme}' in proxy URL: {proxy}")
