import { test, expect, type Page } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";

/**
 * Accessibility gate. Fails on any NEW serious or critical axe-core violation (WCAG 2.0/2.1 A and AA rules).
 *
 * - The public login page is checked on every run, including CI, which has no real Clerk instance.
 * - The signed-in pages need the read-only demo user, so they run when A11Y_DEMO=1 and the API is reachable
 *   (locally, or in CI once Clerk and API secrets are configured). Without it they are skipped, not passed.
 *
 * This is an automated check. It catches only part of WCAG; see docs/accessibility/CHANGELOG.md for what still
 * needs a manual pass.
 */
const TAGS = ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"];
const VIEWPORTS = [
  { name: "1280px", width: 1280, height: 800 },
  { name: "375px", width: 375, height: 812 },
];

async function expectNoBlockingViolations(page: Page) {
  const { violations } = await new AxeBuilder({ page }).withTags(TAGS).analyze();
  const blocking = violations
    .filter((v) => v.impact === "serious" || v.impact === "critical")
    .map((v) => ({ rule: v.id, impact: v.impact, help: v.help, targets: v.nodes.map((n) => n.target.join(" ")).slice(0, 5) }));
  expect(blocking, `serious or critical accessibility violations:\n${JSON.stringify(blocking, null, 2)}`).toEqual([]);
}

async function settle(page: Page) {
  await page.waitForLoadState("networkidle").catch(() => {});
  await page.waitForFunction(() => !document.querySelector(".animate-pulse"), null, { timeout: 15_000 }).catch(() => {});
  await page.waitForTimeout(1200);
}

for (const vp of VIEWPORTS) {
  test(`login page: no serious or critical violations at ${vp.name}`, async ({ page }) => {
    await page.setViewportSize({ width: vp.width, height: vp.height });
    await page.goto("/login");
    await expect(page.getByRole("button", { name: /explore the live demo/i })).toBeVisible();
    await expectNoBlockingViolations(page);
  });
}

test("login page: first Tab stop is the skip link and it targets the main region", async ({ page }) => {
  await page.goto("/login");
  await page.keyboard.press("Tab");
  const skip = page.getByRole("link", { name: /skip to main content/i });
  await expect(skip).toBeFocused();
  await expect(skip).toBeVisible();
  await expect(page.locator("main#main-content")).toHaveCount(1);
});

test("login page: no running animations when the user prefers reduced motion", async ({ page }) => {
  await page.emulateMedia({ reducedMotion: "reduce" });
  await page.goto("/login");
  await page.waitForTimeout(1500);
  const running = await page.evaluate(() =>
    document.getAnimations().filter((a) => a.playState === "running" && (a.effect?.getComputedTiming().iterations ?? 1) === Infinity).length
  );
  expect(running).toBe(0);
});

test.describe("signed-in pages (read-only demo)", () => {
  test.skip(!process.env.A11Y_DEMO, "Set A11Y_DEMO=1 with the app and API running to audit signed-in pages");

  const PAGES = ["/", "/today", "/queue"];

  for (const vp of VIEWPORTS) {
    test(`pages and reminder dialog at ${vp.name}`, async ({ page }) => {
      await page.setViewportSize({ width: vp.width, height: vp.height });
      await page.goto("/login");
      await page.getByRole("button", { name: /explore the live demo/i }).click();
      await page.waitForURL((u) => !u.pathname.startsWith("/login"), { timeout: 60_000 });

      for (const path of PAGES) {
        await page.goto(path);
        await settle(page);
        await expectNoBlockingViolations(page);
      }

      await page.goto("/today");
      await settle(page);
      const href = await page.locator('a[href^="/customers/"]').first().getAttribute("href");
      await page.goto(href!);
      await settle(page);
      await expectNoBlockingViolations(page);

      await page.goto("/queue");
      await settle(page);
      await page.getByRole("button", { name: /remind/i }).first().click();
      await expect(page.getByRole("dialog")).toBeVisible();
      await page.waitForTimeout(800);
      await expectNoBlockingViolations(page);
      await page.keyboard.press("Escape");
      await expect(page.getByRole("dialog")).toHaveCount(0);
    });
  }
});
