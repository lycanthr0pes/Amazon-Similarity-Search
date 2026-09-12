export function productLink(value?: string) {
  if (!value) {
    return undefined;
  }
  try {
    const url = new URL(value);
    if (url.protocol !== "https:" || url.username || url.password) {
      return undefined;
    }
    if (
      url.hostname === "amazon.co.jp" ||
      url.hostname.endsWith(".amazon.co.jp")
    ) {
      const product = url.pathname.match(
        /\/(?:dp|gp\/product|gp\/aw\/d)\/([A-Z0-9]{10})(?:\/|$)/i,
      );
      url.pathname = product
        ? `/dp/${product[1].toUpperCase()}`
        : url.pathname.replace(/^\/-\/en(?=\/|$)/, "") || "/";
      url.searchParams.set("language", "ja_JP");
    }
    return url.href;
  } catch {
    return undefined;
  }
}

export function ProductName({ name, url }: { name: string; url?: string }) {
  const href = productLink(url);
  return (
    <h4>
      {href ? (
        <a href={href} target="_blank" rel="noopener noreferrer">
          {name}
        </a>
      ) : (
        name
      )}
    </h4>
  );
}
