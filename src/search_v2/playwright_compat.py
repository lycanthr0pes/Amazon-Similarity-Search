"""Legacy task-protocol input mapped to Playwright; never sends API credentials."""

import json
import secrets
from urllib.parse import parse_qs, urlsplit

from src.search_v2.outscraper_http import OutscraperHttpResponse
from src.search_v2.playwright_products import MAX_RESPONSE_BYTES, fetch_product_data


class PlaywrightTaskTransport:
    """Synchronous response adapter for archived orchestration interfaces."""

    credential_free = True

    def get(
        self,
        *,
        url,
        params,
        api_key,
        timeout_seconds,
        allow_redirects,
        accept_encoding,
        maximum_response_bytes,
    ):
        # url is an old operation identifier, never a destination for an HTTP request.
        if (
            url != "https://api.outscraper.cloud/amazon-products"
            or not params
            or allow_redirects is not False
            or timeout_seconds != 30
            or accept_encoding != "identity"
            or maximum_response_bytes != MAX_RESPONSE_BYTES
        ):
            raise ValueError("Unsupported legacy product operation")
        queries = []
        for name, value in params:
            if name != "query":
                continue
            if value.startswith("https://"):
                parsed = urlsplit(value)
                if parsed.netloc != "www.amazon.co.jp" or parsed.path != "/s":
                    raise ValueError("Unsupported product search URL")
                values = parse_qs(parsed.query).get("k", [])
                if len(values) != 1:
                    raise ValueError("Invalid product query")
                value = values[0]
            queries.append(value)
        options = {key: value for key, value in params if key != "query"}
        if (
            len(options) != 5
            or options.get("domain") != "amazon.co.jp"
            or options.get("language") != "ja"
            or options.get("limit") != "24"
            or options.get("async") != "true"
        ):
            raise ValueError("Unsupported legacy product options")
        result = fetch_product_data(queries)
        # Retain the original query binding, including old Japanese-search-URL requests.
        original = [value for key, value in params if key == "query"]
        for group, query in zip(result["data"], original, strict=True):
            for product in group:
                product["query"] = query
        body = json.dumps(
            {
                "id": "playwright-" + secrets.token_hex(16),
                "status": "Success",
                "data": result["data"],
            }
        ).encode()
        if len(body) > maximum_response_bytes:
            raise ValueError("Product response exceeded its limit")
        return OutscraperHttpResponse(
            status_code=200,
            content_type="application/json",
            content_length=len(body),
            content_encoding=None,
            body_chunks=(body,),
        )


def uses_playwright(transport):
    for _ in range(5):
        if isinstance(transport, PlaywrightTaskTransport):
            return True
        transport = getattr(transport, "inner", None)
    return False
