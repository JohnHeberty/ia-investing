import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";

test("mission control is navigable and has no serious accessibility violations", async ({
  page,
}) => {
  for (const route of ["/", "/portfolios/demo", "/committee", "/agents", "/data-quality"]) {
    await page.goto(route);
    await expect(page.getByText(/as of/)).toBeVisible();
    const results = await new AxeBuilder({ page }).analyze();
    expect(
      results.violations.filter((item) => ["serious", "critical"].includes(item.impact ?? "")),
    ).toEqual([]);
  }
});

test("primary navigation and theme control work with keyboard only", async ({ page }) => {
  await page.goto("/");
  const risk = page.getByRole("link", { name: "Risco" });
  await risk.focus();
  await page.keyboard.press("Enter");
  await expect(page).toHaveURL(/\/risk$/);
  const theme = page.getByRole("button", { name: "Alternar tema claro ou escuro" });
  await theme.focus();
  await page.keyboard.press("Enter");
  await expect(page.locator("html")).toHaveAttribute("data-theme", "light");
});

test("critical workspaces retain temporal context", async ({ page }) => {
  for (const route of ["/portfolios/demo", "/risk", "/committee", "/agents", "/data-quality"]) {
    await page.goto(route);
    await expect(page.getByText(/as of/)).toBeVisible();
  }
});
