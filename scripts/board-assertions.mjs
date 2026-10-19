import assert from "node:assert/strict";
import { catalogueSections, groupJobs, recommendations } from "../web/public/catalogue.js";

export async function assertBoardContents(page, shown) {
  // Recommendation count comes from eligible data, never an assumed minimum.
  const expected = recommendations(shown);
  assert.equal(await page.locator("#recommendations article").count(), expected.length);
  assert.deepEqual(await page.locator("#recommendations article h3").allTextContents(), expected.map(j => j.vacancy.title));
  if (!expected.length) {
    assert.equal(await page.locator("#recommendations > .muted").textContent(),
      "No top recommendations in this view. Browse the job catalogue below.");
  } else assert.equal(await page.locator("#recommendations > .muted").count(), 0);
  // Catalogue availability is independent of recommendations.
  const actualIds = await page.locator("#jobs article").evaluateAll(cards => cards.map(c => c.dataset.jobId));
  assert.deepEqual(actualIds.toSorted(), shown.map(j => j.id).toSorted());
  assert.equal(new Set(actualIds).size, actualIds.length);
  const groups = groupJobs(shown);
  for (const [i, section] of catalogueSections.entries()) {
    const details = page.locator("#jobs details").nth(i);
    const text = (await details.locator("summary").textContent()).replace("⌄", "");
    assert.equal(text, `${section.label} · ${groups[section.key].length}`);
  }
}
