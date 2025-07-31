import asyncio
import logging
from typing import List, Optional, Dict
import tqdm
from proxy_utils import HTTPMethod, random_headers
from proxy_request import ProxyRequest

logger = logging.getLogger(__name__)


class BruteFetch:
    """BruteFetch class for fetching URLs using multiple proxies with concurrency and retries."""

    def __init__(
        self,
        verify_ssl: bool = True,
        allow_redirects=True,
        max_redirects=10,
        verify_origin=True,
        show_progress: bool = False,
    ):
        self.verify_ssl = verify_ssl
        self.allow_redirects = allow_redirects
        self.max_redirects = max_redirects
        self.verify_origin = verify_origin
        self.show_progress = show_progress
        self.executor = ProxyRequest(
            verify_ssl=verify_ssl,
            allow_redirects=allow_redirects,
            max_redirects=max_redirects,
            verify_origin=verify_origin,
        )

    async def fetch(
        self,
        url: str,
        proxies: List[str],
        headers: Optional[Dict] = None,
        http_method: HTTPMethod = HTTPMethod.GET,
        concurrency_limit: int = 15,
        timeout: float = 3.0,
    ) -> Optional[dict]:
        """Fetch a URL using multiple proxies with concurrency (true worker pool)."""
        if not proxies:
            logger.warning("No proxies provided to BruteFetch.")
            return None

        headers = headers or {}
        for k, v in random_headers().items():
            headers.setdefault(k, v)

        result_container: Dict[str, Optional[dict]] = {"result": None}
        proxy_queue = asyncio.Queue()
        for proxy in proxies:
            await proxy_queue.put(proxy)
        logger.debug("Starting BruteFetch with %d proxies", len(proxies))

        progress = None

        async def worker():
            while not proxy_queue.empty() and not result_container["result"]:
                proxy = await proxy_queue.get()
                try:
                    logger.debug("Trying proxy %s for %s", proxy, url)
                    result = await self.executor.submit(
                        http_method,
                        url,
                        proxy,
                        headers,
                        timeout,
                    )
                    if result and not result_container["result"]:
                        result_container["result"] = {
                            "body": result["body"],
                            "url": result["url"],
                            "status": result["status"],
                            "headers": result["headers"],
                            "used_proxy": proxy,
                            "initial_method": http_method,
                            "final_method": http_method,
                        }
                        logger.info("Successful response via proxy %s", proxy)
                except Exception as e:
                    logger.debug(
                        "Proxy %s failed for %s — %s: %s",
                        proxy,
                        url,
                        type(e).__name__,
                        e,
                    )
                finally:
                    if progress:
                        progress.update(1)

        if self.show_progress:
            progress = tqdm.tqdm(total=len(proxies), desc="BruteFetch", unit="proxy")
        try:
            # Start workers
            workers = [asyncio.create_task(worker()) for _ in range(concurrency_limit)]
            await asyncio.wait(workers, return_when=asyncio.FIRST_COMPLETED)

            # Cancel any remaining workers if result is found
            if result_container["result"]:
                logger.debug("Result found — cancelling pending proxy tasks")
                for w in workers:
                    if not w.done():
                        w.cancel()
                await asyncio.gather(*workers, return_exceptions=True)
            else:
                # Let all workers finish, i.e. all proxies failed
                await asyncio.gather(*workers, return_exceptions=True)
                logger.warning("BruteFetch failed: no proxy succeeded for %s", url)

            if result_container["result"]:
                logger.info(
                    "BruteFetch successful with proxy %s",
                    result_container["result"].get("used_proxy"),
                )
        finally:
            if progress:
                progress.close()

        return result_container["result"]
