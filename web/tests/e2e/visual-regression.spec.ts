import { expect, test } from "@playwright/test";

for (const theme of ["dark", "light"] as const) {
  test(`data-quality operational states remain stable in ${theme} theme`, async ({ page }) => {
    await page.addInitScript(
      (selectedTheme) => localStorage.setItem("ia-theme", selectedTheme),
      theme,
    );
    await page.goto("/data-quality");
    await expect(page.getByText(/as of/)).toBeVisible();
    await expect(page).toHaveScreenshot(`data-quality-${theme}.png`, {
      fullPage: true,
      animations: "disabled",
      caret: "hide",
    });
  });
}
