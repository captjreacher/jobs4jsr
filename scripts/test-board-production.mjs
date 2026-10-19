// Controlled acceptance only. Fixture creation/guarded cleanup are performed by
// the release operator; this script never changes a genuine job's decisions.
import assert from "node:assert/strict";
import { readFile, writeFile, mkdir } from "node:fs/promises";
import { assertBoardContents } from "./board-assertions.mjs";
import { filtered } from "../web/public/app.js";
const { chromium } = await import(process.env.PLAYWRIGHT_MODULE || "playwright");
assert.equal(process.env.JOBS4JSR_PRODUCTION_TEST_APPROVED, "true", "Explicit release-test approval required");
const config = JSON.parse(await readFile(process.env.JOBS4JSR_TEST_CONFIG, "utf8"));
const { origin, fixtureId, fixtureEmployer, cookiesPath, output } = config;
assert.equal(origin, "https://jess.funkmybrand.com");
const cookies = JSON.parse(await readFile(cookiesPath, "utf8"));
await mkdir(output, { recursive: true });
const browser = await chromium.launch({ headless: true, channel: "msedge" });
const context = await browser.newContext();
await context.addCookies(Object.entries(cookies).map(([name, value]) => ({ name, value, domain: "jess.funkmybrand.com", path: "/api", httpOnly: true, secure: true, sameSite: "Strict" })));
let allowFixtureSeen = false;
let unexpectedDecision = false;
// Prevent QA browsing from recording views of Jess's genuine jobs. Only the
// explicitly enabled fixture's real seen requests reach production.
await context.route("**/api/jobs/*/decision", async route => {
  const request = route.request();
  const id = new URL(request.url()).pathname.split("/")[3];
  const action = request.postDataJSON().action;
  if (action === "seen" && id !== fixtureId) return route.fulfill({ json: { ok: true } });
  if (id !== fixtureId) { unexpectedDecision = true; return route.abort(); }
  if (action === "seen" && !allowFixtureSeen) return route.abort();
  return route.continue();
});
const report = { viewports: [], fixtureOnlyWrites: true };
async function jobs() {
  const response = await context.request.get(origin + "/api/jobs");
  assert.equal(response.status(), 200);
  return response.json();
}
async function action(action) {
  const response = await context.request.post(`${origin}/api/jobs/${fixtureId}/decision`, { headers: { Origin: origin }, data: { action } });
  assert.equal(response.status(), 200);
}
async function open(width) {
  const page = await context.newPage();
  await page.setViewportSize({ width, height: 900 });
  page.errors = [];
  page.on("pageerror", error => page.errors.push(error.message));
  await page.goto(origin);
  await page.locator("#board").waitFor({ state: "visible" });
  return page;
}
try {
  const anonymous = await browser.newContext();
  assert.equal((await anonymous.request.get(origin + "/api/jobs")).status(), 401);
  const login = await anonymous.newPage(); await login.goto(origin);
  await login.locator("#login-form").waitFor({ state: "visible" });
  assert.equal(await login.locator("#board").isVisible(), false);
  await anonymous.close();
  const original = (await jobs()).filter(job => job.id !== fixtureId);
  assert.equal(original.length, 11);
  const originalStates = original.map(({id, saved, dismissed, applied, seen_at}) => ({id, saved, dismissed, applied, seen_at})).sort((a,b) => a.id.localeCompare(b.id));
  for (const width of [1280, 390]) {
    const page = await open(width);
    const rows = await jobs();
    await assertBoardContents(page, filtered(rows, "all"));
    assert.equal(await page.locator("#jobs article").count(), 11);
    assert.deepEqual(await page.locator("#jobs details").evaluateAll(ds => ds.map(d => d.open)), [true, true, false]);
    for (const summary of await page.locator("#jobs summary").all()) assert.ok((await summary.boundingBox()).height >= 44);
    assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth));
    assert.match(await page.locator("#health").textContent(), /^Updated (today|yesterday|\d)/);
    await page.screenshot({ path: `${output}/live-${width}.png`, fullPage: true });
    for (const [id, filters] of [["employer", { employer: original[0].vacancy.employer }], ["location", { location: original[0].vacancy.location }]]) {
      await page.locator(`#${id}`).selectOption(Object.values(filters)[0]);
      await assertBoardContents(page, filtered(rows, "all", filters));
      await page.locator(`#${id}`).selectOption("");
    }
    const role = await page.locator("#role option").nth(1).getAttribute("value");
    await page.locator("#role").selectOption(role);
    await assertBoardContents(page, filtered(rows, "all", { role }));
    await page.locator("#role").selectOption("");
    for (const view of ["saved", "applied", "all"]) {
      await page.locator(`[data-tab=${view}]`).click();
      await assertBoardContents(page, filtered(rows, view));
    }
    for (const details of await page.locator("#jobs details").all()) {
      const before = await details.evaluate(d => d.open);
      await details.locator("summary").focus(); await page.keyboard.press("Enter");
      assert.equal(await details.evaluate(d => d.open), !before);
      await page.keyboard.press("Enter");
    }
    assert.deepEqual(page.errors, []);
    report.viewports.push({ width, jobs: 11, counts: true, filters: true, accordions: true, noOverflow: true, emptyRecommendationsValid: true });
    console.log(`PASS live ${width}px: 11 independent jobs, recommendations (including zero), filters, tabs, accordion counts/defaults/keyboard and layout`);
    await page.close();
  }
  const page = await open(1280);
  await page.locator("#employer").selectOption(fixtureEmployer);
  allowFixtureSeen = true;
  const seen = page.waitForResponse(r => r.url().endsWith(`/${fixtureId}/decision`) && r.request().postDataJSON()?.action === "seen");
  await page.locator("#dismissed").check();
  const card = page.locator(`[data-job-id="${fixtureId}"]`);
  await card.scrollIntoViewIfNeeded();
  assert.equal((await seen).status(), 200);
  const state = (await jobs()).find(j => j.id === fixtureId);
  assert.ok(state.seen_at);
  await action("seen");
  assert.equal((await jobs()).find(j => j.id === fixtureId).seen_at, state.seen_at);
  report.fixtureSeenAt = state.seen_at;
  await card.getByRole("button", { name: "Save", exact: true }).click();
  await card.getByRole("button", { name: "Unsave", exact: true }).waitFor();
  await page.locator("[data-tab=saved]").click(); assert.equal(await page.locator("#jobs article").count(), 1);
  await card.getByRole("button", { name: "Applied", exact: true }).click();
  await card.getByRole("button", { name: "Applied ✓", exact: true }).waitFor();
  assert.equal(await card.getByRole("button", { name: "Applied ✓", exact: true }).isDisabled(), true);
  await page.locator("[data-tab=applied]").click(); assert.equal(await page.locator("#jobs article").count(), 1);
  await page.locator("[data-tab=dismissed]").click(); assert.equal(await page.locator("#jobs article").count(), 1);
  await card.getByRole("button", { name: "Restore", exact: true }).click();
  await page.waitForFunction(() => document.querySelectorAll("#jobs article").length === 0);
  await page.locator("[data-tab=applied]").click();
  await card.getByRole("button", { name: "Dismiss", exact: true }).click();
  await card.getByRole("button", { name: "Restore", exact: true }).waitFor();
  await card.getByRole("button", { name: "Unsave", exact: true }).click();
  await card.getByRole("button", { name: "Save", exact: true }).waitFor();
  await page.locator("[data-tab=saved]").click(); assert.equal(await page.locator("#jobs article").count(), 0);
  assert.deepEqual(page.errors, []); await page.close();
  // Fresh authenticated page: only the fixture has been viewed by this test.
  const revisit = await open(390);
  await revisit.locator("#employer").selectOption(fixtureEmployer);
  await revisit.locator("#dismissed").check();
  await assertBoardContents(revisit, filtered(await jobs(), "all", { employer: fixtureEmployer, dismissed: true }));
  assert.equal(await revisit.locator("#jobs details").nth(1).locator("article").count(), 1);
  assert.equal((await jobs()).find(j => j.id === fixtureId).seen_at, state.seen_at);
  assert.deepEqual(revisit.errors, []); await revisit.close();
  const finalStates = (await jobs()).filter(j => j.id !== fixtureId).map(({id, saved, dismissed, applied, seen_at}) => ({id, saved, dismissed, applied, seen_at})).sort((a,b) => a.id.localeCompare(b.id));
  assert.deepEqual(finalStates, originalStates);
  assert.equal(unexpectedDecision, false);
  Object.assign(report, { anonymousDenied: true, savedAppliedDismissedRestore: true, firstSeenPersistsOnRevisit: true, genuineStatesUnchanged: true });
  await writeFile(`${output}/live-acceptance.json`, JSON.stringify(report, null, 2));
  console.log("PASS real fixture Save/Unsave/Applied/Dismiss/Restore and first-seen persistence across visits; genuine job history and decisions unchanged");
} finally {
  await context.close(); await browser.close();
}
