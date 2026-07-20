import { expect, test } from "@playwright/test";

test("mission control loads within performance threshold", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByText(/as of/)).toBeVisible();

  const perfMetrics = await page.evaluate(() => {
    const [nav] = performance.getEntriesByType("navigation") as PerformanceNavigationTiming[];
    return {
      domContentLoaded: nav.domContentLoadedEventEnd - nav.startTime,
      loadEvent: nav.loadEventEnd - nav.startTime,
    };
  });

  expect(perfMetrics.domContentLoaded).toBeLessThan(5000);
  expect(perfMetrics.loadEvent).toBeLessThan(8000);
});

test("data quality loads within performance threshold", async ({ page }) => {
  await page.goto("/data-quality");
  await expect(page.getByText(/as of/)).toBeVisible();

  const perfMetrics = await page.evaluate(() => {
    const [nav] = performance.getEntriesByType("navigation") as PerformanceNavigationTiming[];
    return {
      domContentLoaded: nav.domContentLoadedEventEnd - nav.startTime,
      loadEvent: nav.loadEventEnd - nav.startTime,
    };
  });

  expect(perfMetrics.domContentLoaded).toBeLessThan(5000);
  expect(perfMetrics.loadEvent).toBeLessThan(8000);
});

test("no unused JS chunks larger than 200KB are loaded", async ({ page }) => {
  const resources: string[] = [];
  page.on("response", (response) => {
    const url = response.url();
    if (url.includes(".js")) resources.push(url);
  });

  await page.goto("/");
  await expect(page.getByText(/as of/)).toBeVisible();

  const largeChunks: { url: string; size: number }[] = [];
  for (const url of resources) {
    const response = await page.request.get(url);
    const body = await response.body();
    if (body.length > 200 * 1024) {
      largeChunks.push({ url: url.split("/").pop() ?? url, size: body.length });
    }
  }

  expect(largeChunks).toEqual([]);
});
