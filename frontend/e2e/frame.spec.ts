import { expect, test } from "@playwright/test";

test.use({ deviceScaleFactor: 1 });

test("one-pixel button and window corners retain their stroke coverage at 100%", async ({
  page,
  baseURL,
}) => {
  const origin = new URL(baseURL!).origin;
  await page.route("**/*", async (route) => {
    const url = new URL(route.request().url());
    if (url.origin !== origin || url.pathname.startsWith("/api")) {
      await route.abort("blockedbyclient");
      throw new Error("The frame test attempted an external or API request.");
    }
    await route.continue();
  });
  await page.goto("/");
  await page.evaluate(() => document.fonts.ready);
  const frames = [
    {
      locator: page.getByRole("button", { name: "検索履歴", exact: true }),
      radius: 24,
      minimum: 0.85,
      average: 0.95,
    },
    {
      locator: page.locator("section").first(),
      radius: 15,
      minimum: 0.78,
      average: 0.9,
    },
  ];
  for (const { locator, radius, minimum, average } of frames) {
    const png = await locator.screenshot();
    const coverage = await page.evaluate(
      async ({ bytes, radius }) => {
        const bitmap = await createImageBitmap(
          new Blob([Uint8Array.from(bytes)], { type: "image/png" }),
        );
        const canvas = document.createElement("canvas");
        canvas.width = bitmap.width;
        canvas.height = bitmap.height;
        const context = canvas.getContext("2d")!;
        context.drawImage(bitmap, 0, 0);
        bitmap.close();
        const { data } = context.getImageData(
          0,
          0,
          canvas.width,
          canvas.height,
        );
        const pixel = (x: number, y: number) => {
          if (x < 0 || y < 0 || x >= canvas.width || y >= canvas.height)
            return 0;
          return data[(y * canvas.width + x) * 4] / 255;
        };
        const sample = (x: number, y: number) => {
          x -= 0.5;
          y -= 0.5;
          const ix = Math.floor(x);
          const iy = Math.floor(y);
          const fx = x - ix;
          const fy = y - iy;
          return (
            pixel(ix, iy) * (1 - fx) * (1 - fy) +
            pixel(ix + 1, iy) * fx * (1 - fy) +
            pixel(ix, iy + 1) * (1 - fx) * fy +
            pixel(ix + 1, iy + 1) * fx * fy
          );
        };
        // Integrate across the curve, so normal antialiasing is allowed while
        // a corner that loses much of the intended 1px stroke fails the test.
        const values: number[] = [];
        const peaks: number[] = [];
        for (let degree = 10; degree <= 80; degree++) {
          const angle = (degree * Math.PI) / 180;
          let sum = 0;
          let peak = 0;
          for (let step = -180; step <= 180; step++) {
            const distance = radius - 0.5 + step * 0.02;
            const intensity = sample(
              radius - distance * Math.cos(angle),
              radius - distance * Math.sin(angle),
            );
            sum += intensity * 0.02;
            peak = Math.max(peak, intensity);
          }
          values.push(sum);
          peaks.push(peak);
        }
        // A 1px circular stroke can touch adjacent pixels through antialiasing,
        // but must not paint beyond its geometry plus a pixel's half diagonal.
        let outsideStroke = 0;
        for (let y = 0; y < radius; y++) {
          for (let x = 0; x < radius; x++) {
            const distance = Math.hypot(x + 0.5 - radius, y + 0.5 - radius);
            if (distance > radius + 0.75 || distance < radius - 1.75)
              outsideStroke += pixel(x, y);
          }
        }
        const x = Math.floor(canvas.width / 2);
        return {
          minimum: Math.min(...values),
          minimumPeak: Math.min(...peaks),
          outsideStroke,
          average:
            values.reduce((sum, value) => sum + value, 0) / values.length,
          straightEdge: [pixel(x, 0), pixel(x, 1)],
        };
      },
      { bytes: Array.from(png), radius },
    );
    expect.soft(coverage.minimum).toBeGreaterThan(minimum);
    expect.soft(coverage.average).toBeGreaterThan(average);
    expect.soft(coverage.minimumPeak).toBeGreaterThan(0.65);
    expect.soft(coverage.outsideStroke).toBe(0);
    expect.soft(coverage.straightEdge).toEqual([1, 0]);
  }
});
