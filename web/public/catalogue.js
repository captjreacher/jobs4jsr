export const catalogueSections = [
  { key: "new", label: "NEW", open: true },
  { key: "recent", label: "RECENT", open: true },
  { key: "earlier", label: "EARLIER OPPORTUNITIES", open: false },
];

export function recommendations(rows) {
  return rows.filter(job => job.vacancy.recommended && !job.dismissed && job.vacancy.vacancy_state === "open");
}

// Discovery is a date, so use Auckland calendar days rather than UTC midnights.
function day(value) {
  const parts = new Intl.DateTimeFormat("en-CA", {
    timeZone: "Pacific/Auckland", year: "numeric", month: "2-digit", day: "2-digit",
  }).formatToParts(new Date(value));
  const get = type => parts.find(p => p.type === type).value;
  return `${get("year")}-${get("month")}-${get("day")}`;
}

export function groupJobs(rows, now = new Date()) {
  const groups = { new: [], recent: [], earlier: [] };
  const today = Date.parse(day(now));
  for (const job of rows) {
    const found = Date.parse(job.vacancy.found);
    const age = (today - found) / 86400000;
    const key = !job.seen_at ? "new" : Number.isFinite(age) && age >= 0 && age <= 7 ? "recent" : "earlier";
    groups[key].push(job);
  }
  return groups;
}

export function syncStatus(timestamp, now = new Date()) {
  if (!timestamp) return "Not updated yet";
  const date = new Date(timestamp);
  if (!Number.isFinite(date.getTime())) return "Update time unavailable";
  const age = (Date.parse(day(now)) - Date.parse(day(date))) / 86400000;
  if (age === 0) return "Updated today";
  if (age === 1) return "Updated yesterday";
  return `Updated ${new Intl.DateTimeFormat("en-NZ", {
    timeZone: "Pacific/Auckland", day: "numeric", month: "long",
    ...(day(now).slice(0, 4) !== day(date).slice(0, 4) ? { year: "numeric" } : {}),
  }).format(date)}`;
}
