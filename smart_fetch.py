"""
SmartFetch class for stealthily fetching URLs with multi-proxy support and retries.
Intended to be used with high-quality, reliable proxies.
"""

from typing import Optional
import logging
import asyncio
import aiohttp
from proxy_utils import (
    HTTPMethod,
    ProxyType,
    get_exponential_backoff,
    validate_proxy,
    random_headers,
)
from proxy_request import ProxyRequest

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)


class SmartFetch:
    """SmartFetch class for fetching URLs with multi-proxy support and retries."""

    def __init__(self, verify_ssl=True):
        self.verify_ssl = verify_ssl
        self.executor = ProxyRequest(verify_ssl=verify_ssl)

    async def fetch(
        self,
        url,
        method: HTTPMethod,
        http_proxy: Optional[str],
        socks_proxy: Optional[str],
        http_retries: int,
        socks_retries: int,
        headers: Optional[dict],
        init_timeout: float,
    ):
        """Fetch a URL using the specified proxies and retries."""
        if not http_proxy and not socks_proxy:
            raise ValueError(
                "At least one of 'http_proxy' or 'socks_proxy' must be provided."
            )
        headers = headers or random_headers()

        if http_proxy and not await validate_proxy(http_proxy, ProxyType.HTTP):
            logger.debug("Invalid HTTP proxy: %s", http_proxy)
            http_proxy = None

        if method == HTTPMethod.HEAD and http_proxy:
            for attempt in range(http_retries):
                timeout = get_exponential_backoff(attempt)
                try:
                    result = await self.executor.submit(
                        HTTPMethod.HEAD,
                        url,
                        http_proxy,
                        headers,
                        timeout,
                    )
                    if result:
                        return self._format(
                            result, http_proxy, attempt, method, HTTPMethod.HEAD
                        )
                except (asyncio.TimeoutError, aiohttp.ClientError) as e:
                    logger.debug(
                        "HTTP HEAD attempt %d via proxy %s failed: %s",
                        attempt + 1,
                        http_proxy,
                        type(e).__name__,
                    )
                except Exception as e:
                    logger.exception("Unexpected error during HTTP HEAD: %s", e)

                await asyncio.sleep(get_exponential_backoff(attempt))

        # HTTP GET fallback (1-shot)
        if http_proxy:
            timeout = init_timeout * http_retries
            try:
                result = await self.executor.submit(
                    HTTPMethod.GET, url, http_proxy, headers, timeout
                )
                if result:
                    return self._format(result, http_proxy, 0, method, HTTPMethod.GET)
            except (asyncio.TimeoutError, aiohttp.ClientError) as e:
                logger.debug(
                    "HTTP GET via proxy %s failed: %s", http_proxy, type(e).__name__
                )
            except Exception as e:
                logger.exception("Unexpected error during HTTP GET: %s", e)

        # SOCKS GET fallback
        if socks_proxy:
            for attempt in range(socks_retries):
                timeout = get_exponential_backoff(attempt)
                try:
                    result = await self.executor.submit(
                        HTTPMethod.GET,
                        url,
                        socks_proxy,
                        headers,
                        timeout,
                    )
                    if result:
                        return self._format(
                            result, socks_proxy, attempt, method, HTTPMethod.GET
                        )
                except (asyncio.TimeoutError, aiohttp.ClientError) as e:
                    logger.debug(
                        "SOCKS GET attempt %d via proxy %s failed: %s",
                        attempt + 1,
                        socks_proxy,
                        type(e).__name__,
                    )
                except Exception as e:
                    logger.exception("Unhandled error during SOCKS GET: %s", e)

                await asyncio.sleep(get_exponential_backoff(attempt))

        return None

    def _format(self, result, proxy, retries, initial_method, final_method):
        body, final_url, status, headers_out = result
        return {
            "body": body,
            "url": final_url,
            "status": status,
            "headers": headers_out,
            "used_proxy": proxy,
            "retries": retries,
            "initial_method": initial_method,
            "final_method": final_method,
        }
