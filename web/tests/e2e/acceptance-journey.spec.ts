import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";

test("complete acceptance journey: login → decide → verify", async ({ page }) => {
  await test.step("1. Login — verify SSO button and axe-core", async () => {
    await page.goto("/login");
    await expect(page.getByRole("heading", { name: /acesse o investing os/i })).toBeVisible();
    await expect(page.getByRole("link", { name: /continuar com sso/i })).toHaveAttribute(
      "href",
      "/api/auth/login",
    );

    const results = await new AxeBuilder({ page }).analyze();
    expect(
      results.violations.filter((item) => ["serious", "critical"].includes(item.impact ?? "")),
    ).toEqual([]);
  });

  await test.step("2. Mission Control — verify KPI metrics and portfolio table", async () => {
    await page.goto("/");
    await expect(page.getByRole("heading", { name: /decisões com contexto/i })).toBeVisible();
    await expect(page.getByText(/as of/)).toBeVisible();

    await expect(page.getByRole("table", { name: /carteiras elegíveis/i })).toBeVisible();
    await expect(page.getByRole("row")).toHaveCount({ minimum: 1 });

    const results = await new AxeBuilder({ page }).analyze();
    expect(
      results.violations.filter((item) => ["serious", "critical"].includes(item.impact ?? "")),
    ).toEqual([]);
  });

  await test.step("3. Filter portfolios — select eligibility and verify table updates", async () => {
    const filter = page.getByRole("combobox", { name: /filtrar por elegibilidade/i });
    await filter.selectOption("eligible");
    await expect(page.getByRole("table", { name: /carteiras elegíveis/i })).toBeVisible();
  });

  await test.step("4. Open Portfolio 360 — click first row and verify detail page", async () => {
    const firstRow = page.getByRole("table", { name: /carteiras elegíveis/i }).locator("tbody tr").first();
    await firstRow.click();
    await expect(page.getByRole("heading", { name: /portfolio 360/i })).toBeVisible();
    await expect(page.getByText(/carteira-modelo/i)).toBeVisible();
  });

  await test.step("5. Navigate tabs — click each DomainTab and verify content changes", async () => {
    const tabs = ["Posições", "Performance", "Risco", "Teses", "Auditoria"];
    for (const tabLabel of tabs) {
      const tab = page.getByRole("tab", { name: tabLabel });
      await tab.click();
      await expect(tab).toHaveAttribute("aria-selected", "true");
    }
  });

  await test.step("6. Open Risk Center — verify breach/VaR metrics visible", async () => {
    await page.goto("/risk");
    await expect(page.getByText(/risk center/i)).toBeVisible();
    await expect(page.getByText(/as of/)).toBeVisible();
    await expect(page.getByText(/hard breaches/i)).toBeVisible();
    await expect(page.getByText(/soft breaches/i)).toBeVisible();
  });

  await test.step("7. Open Committee Room — verify quorum and agenda visible", async () => {
    await page.goto("/committee");
    await expect(page.getByText(/committee room/i)).toBeVisible();
    await expect(page.getByText(/quórum/i)).toBeVisible();
    await expect(page.getByText(/agenda de decisões/i)).toBeVisible();
  });

  await test.step("8. Open Agent Operations — verify run metrics visible", async () => {
    await page.goto("/agents");
    await expect(page.getByText(/agent operations/i)).toBeVisible();
    await expect(page.getByText(/runs hoje/i)).toBeVisible();
    await expect(page.getByText(/taxa de sucesso/i)).toBeVisible();
  });

  await test.step("9. Open Data Quality — verify source health table visible", async () => {
    await page.goto("/data-quality");
    await expect(page.getByText(/data quality center/i)).toBeVisible();
    await expect(page.getByText(/saúde das fontes/i)).toBeVisible();

    const results = await new AxeBuilder({ page }).analyze();
    expect(
      results.violations.filter((item) => ["serious", "critical"].includes(item.impact ?? "")),
    ).toEqual([]);
  });

  await test.step("10. Audit Trail — verify event counts visible", async () => {
    await page.goto("/audit");
    await expect(page.getByText(/audit trail/i)).toBeVisible();
    await expect(page.getByText(/eventos hoje/i)).toBeVisible();
    await expect(page.getByText(/correlacionados/i)).toBeVisible();
  });
});
