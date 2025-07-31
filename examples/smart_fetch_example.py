import asyncio
import logging
from typing import Optional
from proxy_utils import random_headers, HTTPMethod
from smart_fetch import SmartFetch

# Set up logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)


async def run_smart_check(
    http_proxy: Optional[str],
    socks_proxy: Optional[str],
) -> Optional[str]:
    """
    Use SmartFetch to perform a multi-stage proxy fetch with retries.
    Returns the HTML body if a working proxy is found.
    """
    smart = SmartFetch(verify_ssl=False)
    result = await smart.fetch(
        url="https://bot.sannysoft.com/",
        method=HTTPMethod.HEAD,
        http_proxy=http_proxy,
        socks_proxy=socks_proxy,
        http_retries=3,
        socks_retries=3,
        headers=random_headers(),
        init_timeout=3.0,
    )
    return result.get("body") if result else None


async def main():
    # Define proxies here
    http_proxy = "http://127.0.0.1:8080"
    socks_proxy = "socks5://127.0.0.1:9050"

    logger.info("Using HTTP proxy: %s", http_proxy)
    logger.info("Using SOCKS proxy: %s", socks_proxy)

    html = await run_smart_check(http_proxy, socks_proxy)

    if html:
        print("✅ Successfully fetched response:")
        print(html[:1000])
    else:
        print("❌ No working proxy path succeeded.")


if __name__ == "__main__":
    asyncio.run(main())
