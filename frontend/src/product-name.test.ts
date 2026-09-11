import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import { ProductName } from "./product-name";

describe("product name links", () => {
  it("renders the supplied HTTPS product page as a new-tab link", () => {
    const html = renderToStaticMarkup(
      createElement(ProductName, {
        name: "Synthetic product",
        url: "https://example.com/products/1",
      }),
    );
    expect(html).toContain('href="https://example.com/products/1"');
    expect(html).toContain('target="_blank"');
    expect(html).toContain('rel="noopener noreferrer"');
    expect(html).toContain(">Synthetic product</a>");
  });
  it.each([
    undefined,
    "",
    "/products/1",
    "javascript:alert(1)",
    "data:text/html,test",
    "https://user:password@example.com/1",
  ])("keeps missing or unsuitable URLs as text: %s", (url) => {
    const html = renderToStaticMarkup(
      createElement(ProductName, { name: "Mock product", url }),
    );
    expect(html).toBe("<h4>Mock product</h4>");
  });
});
