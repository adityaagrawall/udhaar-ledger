// Accessibility audit harness: axe-core (via Playwright) + Lighthouse (accessibility category).
//
//   node a11y/audit.mjs --out ../docs/accessibility/before --base http://localhost:3100
//
// It signs in through the public "Explore the live demo" button (read-only viewer), then audits each
// page at 1280px and 375px. Raw tool output is written untouched to the output folder. Nothing here
// estimates a number: every figure in the summary is read back from these files.
import { chromium } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";
import lighthouse from "lighthouse";
import { mkdirSync, writeFileSync, rmSync, mkdtempSync } from "node:fs";
import { tmpdir } from "node:os";
import path from "node:path";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const arg = (name, fallback) => {
  const i = process.argv.indexOf(`--${name}`);
  return i > -1 ? process.argv[i + 1] : fallback;
};
const BASE = arg("base", "http://localhost:3100");
const OUT = path.resolve(arg("out", "../docs/accessibility/before"));
const PORT = Number(arg("port", "9333"));
const ONLY = arg("only", ""); // comma separated page ids, for quick re-runs

const VIEWPORTS = [
  { id: "1280", width: 1280, height: 800, mobile: false },
  { id: "375", width: 375, height: 812, mobile: true },
];
const WCAG_TAGS = ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"];

mkdirSync(OUT, { recursive: true });
const write = (name, data) => writeFileSync(path.join(OUT, name), JSON.stringify(data, null, 2));

async function settle(page) {
  await page.waitForLoadState("networkidle").catch(() => {});
  await page.waitForFunction(() => !document.querySelector(".animate-pulse"), null, { timeout: 15000 }).catch(() => {});
  await page.waitForTimeout(1500); // count-up animations run for 0.9s
}

async function layoutMetrics(page) {
  return page.evaluate(() => {
    const vw = document.documentElement.clientWidth;
    const main = document.querySelector("main");
    const small = [];
    const sel = 'a[href],button,input:not([type=hidden]),select,textarea,summary,[role=button],[role=radio],[role=tab]';
    for (const el of document.querySelectorAll(sel)) {
      const r = el.getBoundingClientRect();
      const cs = getComputedStyle(el);
      if (r.width === 0 || r.height === 0 || cs.visibility === "hidden" || cs.display === "none") continue;
      if (el.closest("[aria-hidden=true]")) continue;
      // Skip sr-only helpers and anything fully off-screen.
      if (r.width <= 1 || r.height <= 1) continue;
      if (r.width < 44 || r.height < 44) {
        small.push({
          tag: el.tagName.toLowerCase(),
          name: (el.getAttribute("aria-label") || el.textContent || el.getAttribute("placeholder") || "").trim().slice(0, 40),
          w: Math.round(r.width),
          h: Math.round(r.height),
        });
      }
    }
    return {
      viewportWidth: vw,
      documentOverflowPx: document.documentElement.scrollWidth - vw,
      mainOverflowPx: main ? main.scrollWidth - main.clientWidth : 0,
      targetsUnder44px: small.length,
      targetsUnder44pxSample: small.slice(0, 15),
    };
  });
}

async function runAxe(page) {
  const res = await new AxeBuilder({ page }).withTags(WCAG_TAGS).analyze();
  return {
    axeVersion: res.testEngine?.version,
    url: res.url,
    violations: res.violations,
    incomplete: res.incomplete.map((v) => ({ id: v.id, impact: v.impact, help: v.help, nodes: v.nodes.length })),
    passes: res.passes.length,
  };
}

async function runLighthouse(url, vp) {
  const flags = {
    port: PORT,
    output: "json",
    logLevel: "error",
    onlyCategories: ["accessibility"],
    disableStorageReset: true,
    throttlingMethod: "provided",
    formFactor: vp.mobile ? "mobile" : "desktop",
    screenEmulation: { mobile: vp.mobile, width: vp.width, height: vp.height, deviceScaleFactor: vp.mobile ? 2 : 1, disabled: false },
    skipAudits: ["full-page-screenshot", "screenshot-thumbnails", "final-screenshot", "final-screenshot"],
  };
  const r = await lighthouse(url, flags);
  return r.lhr;
}

const PAGES = [
  { id: "login", label: "Demo login", path: "/login", auth: false },
  { id: "overview", label: "Landing (Overview)", path: "/", auth: true },
  { id: "today", label: "Daily call list", path: "/today", auth: true },
  { id: "account", label: "Account detail", path: null, auth: true }, // resolved from /today
  { id: "queue", label: "Invoice queue (reminders)", path: "/queue", auth: true },
];

// States that need interaction first. axe only (Lighthouse navigation mode cannot open dialogs).
const STATES = [
  {
    id: "today-why-open",
    label: "Daily list, 'Why this lane' expanded",
    path: "/today",
    act: async (page) => {
      await page.getByRole("button", { name: /why this lane/i }).first().click();
      await page.waitForTimeout(600);
    },
  },
  {
    id: "reminder-dialog",
    label: "Reminder approval dialog",
    path: "/queue",
    act: async (page) => {
      await page.getByRole("button", { name: /remind/i }).first().click();
      await page.waitForSelector('[role="dialog"]');
      await page.waitForFunction(() => !document.body.innerText.includes("Generating"), null, { timeout: 15000 }).catch(() => {});
      await page.waitForTimeout(800);
    },
  },
  {
    id: "mobile-nav-open",
    label: "Mobile navigation drawer open",
    path: "/today",
    only: "375",
    act: async (page) => {
      await page.getByRole("button", { name: /open navigation/i }).click();
      await page.waitForTimeout(600);
    },
  },
];

const userDataDir = mkdtempSync(path.join(tmpdir(), "a11y-audit-"));
const context = await chromium.launchPersistentContext(userDataDir, {
  headless: true,
  // Optional: reuse an already installed Chromium instead of the build Playwright pins.
  ...(process.env.A11Y_CHROMIUM ? { executablePath: process.env.A11Y_CHROMIUM } : {}),
  args: [`--remote-debugging-port=${PORT}`],
  viewport: { width: 1280, height: 800 },
});
const page = context.pages()[0] ?? (await context.newPage());

const meta = {
  base: BASE,
  startedAt: new Date().toISOString(),
  tools: {
    lighthouse: require("lighthouse/package.json").version,
    axeCore: require("axe-core/package.json").version,
    playwright: require("@playwright/test/package.json").version,
    chromium: context.browser()?.version(),
  },
  wcagTags: WCAG_TAGS,
  pages: [],
};
const only = ONLY ? ONLY.split(",") : null;
const wanted = (id) => !only || only.includes(id);

async function auditPage(def, url, vp) {
  await page.setViewportSize({ width: vp.width, height: vp.height });
  await page.goto(url, { waitUntil: "domcontentloaded" });
  await settle(page);
  const key = `${def.id}-${vp.id}`;
  write(`axe-${key}.json`, await runAxe(page));
  write(`layout-${key}.json`, await layoutMetrics(page));
  const lhr = await runLighthouse(url, vp);
  write(`lighthouse-${key}.json`, lhr);
  const a = lhr.categories.accessibility.score;
  console.log(`  ${key.padEnd(18)} lighthouse=${a === null ? "n/a" : Math.round(a * 100)}`);
  meta.pages.push({ id: def.id, label: def.label, url, kind: "page", viewport: vp.id });
}

// 1) Unauthenticated: demo login
for (const vp of VIEWPORTS) {
  if (wanted("login")) await auditPage(PAGES[0], `${BASE}/login`, vp);
}

// 2) Sign in with the public demo button
await page.setViewportSize({ width: 1280, height: 800 });
await page.goto(`${BASE}/login`, { waitUntil: "domcontentloaded" });
await page.getByRole("button", { name: /explore the live demo/i }).click({ timeout: 30000 });
await page.waitForURL((u) => !u.pathname.startsWith("/login"), { timeout: 60000 });
await settle(page);

// Resolve an account detail URL from the first account link on /today
await page.goto(`${BASE}/today`, { waitUntil: "domcontentloaded" });
await settle(page);
const accountHref = await page.locator('a[href^="/customers/"]').first().getAttribute("href");
PAGES[3].path = accountHref;
console.log(`account detail page: ${accountHref}`);

for (const def of PAGES.filter((p) => p.auth)) {
  if (!wanted(def.id)) continue;
  console.log(def.label);
  for (const vp of VIEWPORTS) await auditPage(def, `${BASE}${def.path}`, vp);
}

// 3) Interactive states (axe + layout only)
for (const st of STATES) {
  if (!wanted(st.id)) continue;
  console.log(st.label);
  for (const vp of VIEWPORTS) {
    if (st.only && st.only !== vp.id) continue;
    await page.setViewportSize({ width: vp.width, height: vp.height });
    await page.goto(`${BASE}${st.path}`, { waitUntil: "domcontentloaded" });
    await settle(page);
    await st.act(page);
    const key = `${st.id}-${vp.id}`;
    write(`axe-${key}.json`, await runAxe(page));
    write(`layout-${key}.json`, await layoutMetrics(page));
    meta.pages.push({ id: st.id, label: st.label, url: `${BASE}${st.path}`, kind: "state", viewport: vp.id });
    console.log(`  ${key}`);
  }
}

// 4) Reflow: horizontal overflow at 200% zoom (640 CSS px), 375 and 320
meta.reflow = {};
for (const w of [640, 375, 320]) {
  for (const def of PAGES.filter((p) => p.auth)) {
    if (!wanted(def.id)) continue;
    await page.setViewportSize({ width: w, height: 800 });
    await page.goto(`${BASE}${def.path}`, { waitUntil: "domcontentloaded" });
    await settle(page);
    const m = await layoutMetrics(page);
    (meta.reflow[def.id] ??= {})[w] = { documentOverflowPx: m.documentOverflowPx, mainOverflowPx: m.mainOverflowPx };
  }
}

meta.finishedAt = new Date().toISOString();
write("meta.json", meta);
await context.close();
rmSync(userDataDir, { recursive: true, force: true });
console.log(`done -> ${OUT}`);
process.exit(0);
