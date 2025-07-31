# ScrapeLib

A modular Python library for web scraping. Comes with two primary scraping methods, SmartFetch for slow, methodical retries with reliable proxies and BruteFetch for rapidly running through a large pool of free/garbage proxies.

---

### Installing dependencies

```bash
pip install aiohttp aiohttp-socks lxml tqdm
```

---

## Features

### SmartFetch

Optimized for retry logic with exponential backoff and high-quality proxies. Supports both HEAD and GET requests as needed.  
The default request sequence is:

```
HTTP HEAD ×3 → HTTP GET → SOCKS GET ×3
```

| Option         | Description                                                                 |
|----------------|-----------------------------------------------------------------------------|
| `http_proxy`   | HTTP proxy to use. Will always be tried first.                              |
| `socks_proxy`  | SOCKS proxy fallback. Optional, but at least one proxy (HTTP or SOCKS) must be provided. |
| `http_retries` | Number of retry attempts for HTTP HEAD requests.                            |
| `socks_retries`| Number of retry attempts for SOCKS GET requests.                            |
| `headers`      | Optional custom headers. If not provided, randomized realistic browser headers are used. |
| `init_timeout` | Initial request timeout (used in calculating backoff delays).               |

---

### BruteFetch

Built for high-concurrency brute-force URL resolution using large proxy pools. Executes parallel fetch attempts and returns the first successful result.  
Ideal for scraping with unreliable or anonymous proxies.

| Option             | Description                                                                 |
|--------------------|-----------------------------------------------------------------------------|
| `url`              | The target URL to fetch.                                                    |
| `proxies`          | A list of HTTP or SOCKS proxy strings. Each will be tried concurrently until one succeeds. |
| `http_method`      | HTTP method to use (GET, HEAD, etc.). Defaults to GET.                      |
| `headers`          | Optional dictionary of HTTP headers. Random realistic headers will be used by default. |
| `concurrency_limit`| Number of concurrent worker tasks fetching with different proxies.          |
| `timeout`          | Per-request timeout in seconds. Applies to each proxy attempt individually. |
| `show_progress`    | Enables a live progress bar with tqdm showing proxy usage (if enabled in constructor). |

---

### ProxyRequest

Core HTTP handler that executes a single request through a specified proxy. Supports both HTTP and SOCKS proxies, with built-in support for redirects, binary-safe response handling, and optional origin verification to detect proxy hijacks.

| Option             | Description                                                                 |
|--------------------|-----------------------------------------------------------------------------|
| `method`           | The HTTP method to use (GET, HEAD, etc.) from the HTTPMethod enum.          |
| `url`              | The target URL to request.                                                  |
| `proxy`            | The full proxy URL string (e.g., http://... or socks5://...). Automatically infers proxy type. |
| `headers`          | Dictionary of HTTP headers. Falls back to randomized realistic headers if omitted or invalid. |
| `timeout`          | Timeout for the request in seconds.                                         |

**Constructor Flags:**

| Flag               | Description                                                                 |
|--------------------|-----------------------------------------------------------------------------|
| `verify_ssl`       | Whether to verify SSL certificates.                                         |
| `allow_redirects`  | Enable or disable following HTTP redirects.                                 |
| `max_redirects`    | Maximum number of redirects to follow.                                      |
| `verify_origin`    | If True, ensures the final response URL matches the original domain to detect hijacks. |

Both SmartFetch and BruteFetch use this class for fetching. Use those when fetching URLs with your desired logic.

---

### proxy_utils

A utility module providing enums, helpers, and tools for proxy handling, request construction, and HTML parsing.

#### Enums

| Name         | Description                            |
|--------------|----------------------------------------|
| `HTTPMethod` | Enum of supported HTTP verbs (GET, HEAD, POST, PUT, DELETE). |
| `ProxyType`  | Enum for proxy classification (HTTP, SOCKS). |

#### Helper Functions

| Function                       | Description |
|--------------------------------|-------------|
| `random_headers()`            | Generates realistic, randomized browser HTTP headers (Chrome, Firefox, Safari). |
| `get_exponential_backoff()`   | Computes retry delays using exponential backoff with optional jitter. |
| `validate_proxy()`            | Tests if a proxy is valid and reachable by making a GET request to a known IP service. |
| `infer_type()`                | Determines whether a proxy string is HTTP or SOCKS based on its scheme. |
| `parse_html_for_license()`    | Extracts copyright/license metadata from HTML using meta tags, regex, and JSON-LD. |
| `sanitize_filename()`         | Sanitizes a string to be safely used as a filename by removing/escaping problematic characters. |
