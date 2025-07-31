import asyncio
import json
import logging
from typing import List, Optional
from proxy_utils import random_headers, HTTPMethod
from brute_fetch import BruteFetch

# Path to your proxy list file
PROXIES = "proxies.json"

# PROXIES SHOULD BE FORMATTED AS A LIST
# [
#    "http://proxy1:port",
#    "socks4://proxy2:port",
#    "socks5://proxy3:port"
# ]

# Set up logging (DEBUG for demonstration)
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)


async def run_brute_check(proxies: List[str]) -> Optional[str]:
    """
    Use BruteFetch to check which proxy works for the target.
    Returns the HTML response body from the first working proxy.
    """
    brute = BruteFetch(verify_ssl=False)
    result = await brute.fetch(
        url="https://bot.sannysoft.com/",
        proxies=proxies,
        headers=random_headers(),
        http_method=HTTPMethod.GET,
        concurrency_limit=20,
        timeout=5.0,
    )
    return result.get("body") if result else None


async def main():
    with open(PROXIES, "r", encoding="utf-8") as f:
        proxies = json.load(f)

    logger.info("Loaded %d proxies", len(proxies))

    html = await run_brute_check(proxies)

    if html:
        print("✅ Successfully fetched response:")
        print(html[:1000])
    else:
        print("❌ No working proxy found.")


if __name__ == "__main__":
    asyncio.run(main())
