"""Make HTTP requests through a proxy using aiohttp and aiohttp_socks."""

import asyncio
import logging
import time
from urllib.parse import urlparse
import aiohttp
from aiohttp import ClientTimeout
from aiohttp_socks import ProxyConnector
from proxy_utils import HTTPMethod, ProxyType, random_headers, infer_type

logger = logging.getLogger(__name__)


class ProxyOriginMismatchError(Exception):
    """Exception raised when the proxy response does not match the expected origin."""

    def __init__(self, expected_host: str, actual_host: str, url: str):
        self.expected_host = expected_host
        self.actual_host = actual_host
        self.url = url
        super().__init__(self._build_message())

    def _build_message(self):
        return (
            f"Expected host '{self.expected_host}' but got '{self.actual_host}' "
            f"from response URL '{self.url}'. Possible proxy hijack."
        )


class ProxyRequest:
    """Class to handle HTTP requests through a proxy."""

    def __init__(
        self,
        verify_ssl=True,
        allow_redirects=True,
        max_redirects=10,
        verify_origin=True,
    ):
        self.verify_ssl = verify_ssl
        self.allow_redirects = allow_redirects
        self.max_redirects = max_redirects
        self.verify_origin = (
            verify_origin  # Prevent proxy from pretending to be the target
        )

    async def submit(
        self,
        method: HTTPMethod,
        url: str,
        proxy: str,
        headers: dict,
        timeout: float,
    ):
        """
        Submit an HTTP request through a specified proxy, with redirect and binary-safe handling.
        """
        if not isinstance(headers, dict):
            logger.warning("Invalid header, defaulting to random headers.")
            headers = random_headers()
        proxy_type = infer_type(proxy)
        try:
            client_timeout = ClientTimeout(total=timeout)

            # Choose connector based on proxy type
            connector = (
                aiohttp.TCPConnector(ssl=self.verify_ssl)
                if proxy_type == ProxyType.HTTP
                else ProxyConnector.from_url(proxy, ssl=self.verify_ssl)
            )

            logger.debug(
                "Preparing request: method=%s, url=%s, proxy=%s (%s), headers=%s, timeout=%ss",
                method.name,
                url,
                proxy,
                proxy_type.name,
                headers,
                timeout,
            )

            async with aiohttp.ClientSession(
                connector=connector,
                headers=headers,
                raise_for_status=False,  # Do not raise an exception for HTTP errors (400, 500)
                trust_env=False,  # Do not allow proxy env variables to override
                timeout=client_timeout,
            ) as session:
                req_method = getattr(session, method.name.lower())
                if req_method is None:
                    raise ValueError(f"Unsupported HTTP method: {method.name}")
                start = time.monotonic()

                async with req_method(
                    url,
                    allow_redirects=self.allow_redirects,
                    max_redirects=self.max_redirects,
                ) as resp:
                    elapsed = time.monotonic() - start

                    if self.verify_origin:
                        original_host = urlparse(url).hostname or ""
                        final_host = urlparse(str(resp.url)).hostname or ""
                        if original_host != final_host:
                            raise ProxyOriginMismatchError(
                                original_host, final_host, str(resp.url)
                            )

                    if self.allow_redirects and resp.history:
                        logger.debug(
                            "Redirect chain (%d): %s",
                            len(resp.history),
                            " -> ".join(str(r.url) for r in resp.history + (resp,)),
                        )

                    content_type = resp.headers.get("Content-Type", "").lower()
                    is_text = any(x in content_type for x in ("text", "json", "xml"))

                    if is_text:
                        try:
                            body = await resp.text()
                        except UnicodeDecodeError:
                            logger.warning(
                                "Failed to decode text response; falling back to raw bytes."
                            )
                            body = await resp.read()
                    else:
                        body = await resp.read()

                    logger.debug(
                        "Response received: %s %s -> %d (%s) in %.2fs | %d bytes",
                        method.name,
                        resp.url,
                        resp.status,
                        content_type or "unknown",
                        elapsed,
                        len(body) if body else 0,
                    )

                    return {
                        "body": body,
                        "url": str(resp.url),
                        "status": resp.status,
                        "headers": dict(resp.headers),
                    }

        except aiohttp.ClientConnectorCertificateError as e:
            logger.info(
                "SSL certificate validation failed for %s via %s proxy %s. "
                "If you're intentionally targeting an untrusted host, set verify_ssl=False. Error: %s",
                url,
                proxy_type.name,
                proxy,
                e,
            )
        except (
            asyncio.TimeoutError,
            aiohttp.ClientConnectionError,
            aiohttp.ClientResponseError,
            aiohttp.ClientPayloadError,
            aiohttp.ClientError,
        ) as e:
            logger.warning(
                "%s on %s via %s proxy %s: %s",
                type(e).__name__,
                url,
                proxy_type.name,
                proxy,
                e,
            )
            return {
                "error": str(e),
                "url": url,
                "proxy": proxy,
                "status": None,
                "body": None,
                "headers": {},
            }
