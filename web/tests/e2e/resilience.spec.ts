import { expect, test } from "@playwright/test";

test("session expiry redirects to login", async ({ page }) => {
  await page.context().clearCookies();
  await page.route("**/api/auth/session", (route) =>
    route.fulfill({ status: 401, contentType: "application/json", body: JSON.stringify({ error: "unauthorized" }) }),
  );
  await page.goto("/");
  await expect(page).toHaveURL(/\/login/);
  await expect(page.getByRole("heading", { name: /acesse o investing os/i })).toBeVisible();
});

test("API failure shows error state", async ({ page }) => {
  await page.route("**/api/backend/api/v1/agent-runs*", (route) =>
    route.fulfill({ status: 500, contentType: "application/json", body: JSON.stringify({ error: "internal_server_error" }) }),
  );
  await page.goto("/agents");
  await expect(page.getByText(/agent operations/i)).toBeVisible();
  const errorPanel = page.locator("[data-state='error']");
  await expect(errorPanel).toBeVisible();
});

test("missing data shows empty state", async ({ page }) => {
  await page.goto("/portfolios/invalid-id");
  await expect(page.getByText(/portfolio 360/i)).toBeVisible();
  const statePanel = page.locator("[data-state]");
  await expect(statePanel.first()).toBeVisible();
});
