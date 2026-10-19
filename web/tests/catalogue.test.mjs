import test from "node:test";
import assert from "node:assert/strict";
import { groupJobs, syncStatus, catalogueSections } from "../public/catalogue.js";
import { filtered } from "../public/app.js";
const now = new Date("2026-10-19T00:00:00Z");
const job = (id, found, seen_at = "2026-10-18T00:00:00Z", flags = {}) => ({
  id, seen_at, ...flags, vacancy: { found, title: "Waiter", employer: "Hotel", location: "CBD" },
});
test("unseen overrides age and discovery-run flag; seven calendar days inclusive; no duplicates", () => {
  const rows = [job("new", "2020-01-01", null), job("today", "2026-10-19"), job("boundary", "2026-10-12"), job("old", "2026-10-11"), job("unknown", undefined)];
  const groups = groupJobs(rows, now);
  assert.deepEqual(groups.new.map(j => j.id), ["new"]);
  assert.deepEqual(groups.recent.map(j => j.id), ["today", "boundary"]);
  assert.deepEqual(groups.earlier.map(j => j.id), ["old", "unknown"]);
  assert.equal(new Set(Object.values(groups).flat().map(j => j.id)).size, rows.length);
});
test("all existing filters apply before grouping and restoration changes visibility", () => {
  const rows = [job("saved", "2026-10-19", null, {saved:true}), job("applied", "2026-10-12", undefined, {applied:true}), job("dismissed", "2026-10-01", undefined, {dismissed:true})];
  const ids = (view, filters) => Object.values(groupJobs(filtered(rows, view, filters), now)).flat().map(j => j.id);
  assert.deepEqual(ids("saved"), ["saved"]);
  assert.deepEqual(ids("applied"), ["applied"]);
  assert.deepEqual(ids("dismissed"), ["dismissed"]);
  assert.equal(ids("all").length, 2);
  assert.equal(ids("all", {dismissed:true}).length, 3);
  for (const filter of [{employer:"Other"}, {role:"Café"}, {location:"Other"}]) assert.equal(ids("all", filter).length, 0);
  rows[2].dismissed = false;
  assert.equal(ids("all").length, 3);
});
test("accordion defaults", () => assert.deepEqual(catalogueSections.map(s => s.open), [true,true,false]));

test("first release: all eleven historical jobs are NEW, including the saved job", () => {
  const rows = Array.from({ length: 11 }, (_, i) => job(String(i), "2026-10-14", null, { saved: i === 0 }));
  const groups = groupJobs(filtered(rows, "all"), now);
  assert.deepEqual(Object.values(groups).map(rows => rows.length), [11, 0, 0]);
  assert.equal(groupJobs(filtered(rows, "saved"), now).new.length, 1);
  assert.equal(rows[0].saved, true);
});
test("sync status uses Auckland calendar dates and readable fallback", () => {
  assert.equal(syncStatus("2026-10-18T13:00:52.159747+00:00", now), "Updated today");
  assert.equal(syncStatus("2026-10-17T13:00:00Z", now), "Updated yesterday");
  assert.equal(syncStatus("2026-10-01T00:00:00Z", now), "Updated 1 October");
  assert.equal(syncStatus(null, now), "Not updated yet");
  assert.equal(syncStatus("invalid", now), "Update time unavailable");
});
