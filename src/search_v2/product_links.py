"""Display Amazon Japan products with an explicit Japanese language preference."""

import re
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit


def japanese_product_url(value):
    if not isinstance(value, str):
        return None
    try:
        url = urlsplit(value)
        host = url.hostname or ""
        if (
            url.scheme != "https"
            or url.username
            or url.password
            or url.port not in {None, 443}
            or not (host == "amazon.co.jp" or host.endswith(".amazon.co.jp"))
        ):
            return None
        product = re.search(r"/(?:dp|gp/product|gp/aw/d)/([A-Z0-9]{10})(?:/|$)", url.path, re.I)
        path = (
            f"/dp/{product[1].upper()}"
            if product
            else re.sub(r"^/-/en(?=/|$)", "", url.path) or "/"
        )
        query = [
            (key, val)
            for key, val in parse_qsl(url.query, keep_blank_values=True)
            if key != "language"
        ]
        query.append(("language", "ja_JP"))
        return urlunsplit(("https", host, path, urlencode(query), ""))
    except (TypeError, ValueError):
        return None
