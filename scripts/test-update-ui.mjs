// Local fictional preview only. No real identities, requests or discovery.
const { chromium } = await import(process.env.PLAYWRIGHT_MODULE || "playwright");
import assert from "node:assert/strict";
import { mkdir } from "node:fs/promises";
const browser = await chromium.launch({ headless: true, channel: "msedge" });
await mkdir("tmp/manual-update-evidence", { recursive: true });
try {
  for (const width of [1280, 390]) {
    const page = await browser.newPage({ viewport: { width, height: 900 } });
    const errors = []; page.on("pageerror", error => errors.push(error.message));
    const rows = [{ id: "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa", saved: true, seen_at: "2026-01-01",
      vacancy: { employer: "Fictional Hotel", title: "Waiter", location: "CBD", found: "2026-01-01", match: 80, vacancy_state: "open" } }];
    let status = { request: null, runner: { online: true, busy: false } }, submissions = 0, loads = 0;
    await page.route("**/api/**", async route => {
      const path = new URL(route.request().url()).pathname;
      let json;
      if (path === "/api/update-status") json = status;
      else if (path === "/api/update-requests") {
        submissions++;
        assert.match(route.request().postDataJSON().key, /^[a-f0-9-]{36}$/);
        status = { request: { id: "request-1", state: "queued" }, runner: { online: false, busy: false } };
        json = status.request;
      } else if (path === "/api/health") json = { sync: [], sources: [] };
      else { loads++; json = rows; }
      await route.fulfill({ json });
    });
    await page.goto("http://127.0.0.1:8790");
    const button = page.getByRole("button", { name: "Run Update", exact: true });
    await page.waitForFunction(() => !document.getElementById("run-update").disabled);
    assert.ok((await button.boundingBox()).height >= 44);
    assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth));
    await page.locator("#employer").selectOption("Fictional Hotel");
    await page.locator("[data-tab=saved]").click();
    await page.locator("#jobs details").nth(2).locator("summary").click();
    await button.click();
    await page.waitForFunction(() => document.getElementById("update-status").textContent.includes("offline"));
    assert.equal(await page.locator("#run-update").isDisabled(), true);
    assert.equal(submissions, 1);
    await page.screenshot({ path: `tmp/manual-update-evidence/${width}-requested.png`, fullPage: true });
    status = { ...status, request: { ...status.request, state: "running" }, runner: { online: true, busy: true } };
    await page.getByRole("button", { name: "Running update", exact: true }).waitFor({ timeout: 10000 });
    status = { ...status, request: { id: "request-1", state: "completed", summary: { new_jobs: 2, refreshed_jobs: 8, source_failures: ["Employer A"] } }, last_successful_update: new Date().toISOString() };
    await page.waitForFunction(() => document.getElementById("update-status").textContent.includes("Update completed"), { timeout: 10000 });
    await page.waitForFunction(() => document.getElementById("health").textContent === "Updated today");
    assert.ok(loads >= 2, "completion must refresh catalogue");
    assert.equal(await page.locator("#employer").inputValue(), "Fictional Hotel");
    assert.equal(await page.locator("[data-tab=saved]").getAttribute("aria-pressed"), "true");
    assert.equal(await page.locator("#jobs details").nth(2).evaluate(d => d.open), true);
    assert.match(await page.locator("#update-status").textContent(), /2 new jobs.*8 existing jobs refreshed.*Employer A/);
    assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth));
    assert.deepEqual(errors, []);
    await page.screenshot({ path: `tmp/manual-update-evidence/${width}-completed.png`, fullPage: true });
    await page.close();
    console.log(`PASS ${width}px: Run Update touch target, one submission, durable/offline/running/completed states, warnings, refresh and preserved filters/accordions`);
  }
} finally { await browser.close(); }
