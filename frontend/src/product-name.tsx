function productLink(value?: string) {
  if (!value) {
    return undefined;
  }
  try {
    const url = new URL(value);
    return url.protocol === "https:" && !url.username && !url.password
      ? url.href
      : undefined;
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
