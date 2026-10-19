import { openLetterEditor, clearLetterDrafts } from "./cover-letter.js";
import { groupJobs, syncStatus, catalogueSections } from "./catalogue.js";
let observer;
const observed = new Set();
const expanded = new Map();
let jobs = [],
  tab = "all";
const $ = (id) => document.getElementById(id);
async function api(path, options = {}) {
  const r = await fetch("/api" + path, {
    ...options,
    headers: { "Content-Type": "application/json" },
  });
  const body = await r.json();
  if (!r.ok)
    throw Object.assign(new Error(body.error || "Please try again"), {
      status: r.status,
    });
  return body;
}
function el(tag, text, cls) {
  const e = document.createElement(tag);
  if (text !== undefined) e.textContent = text;
  if (cls) e.className = cls;
  return e;
}
function role(title) {
  return /cafe|café/i.test(title)
    ? "Café"
    : /food.*beverage/i.test(title)
      ? "Food & Beverage"
      : /guest/i.test(title)
        ? "Guest Service"
        : /host/i.test(title)
          ? "Host"
          : "Front of House";
}
export function filtered(rows, view, filters = {}) {
  return rows
    .filter(
      (j) =>
        (view === "dismissed"
          ? j.dismissed
          : filters.dismissed || !j.dismissed) &&
        (view !== "saved" || j.saved) &&
        (view !== "applied" || j.applied) &&
        (!filters.employer || j.vacancy.employer === filters.employer) &&
        (!filters.role || role(j.vacancy.title) === filters.role) &&
        (!filters.location || j.vacancy.location === filters.location),
    )
    .sort(
      (a, b) =>
        Number(b.vacancy.is_new) - Number(a.vacancy.is_new) ||
        (b.vacancy.match || 0) - (a.vacancy.match || 0) ||
        (b.vacancy.posted || "").localeCompare(a.vacancy.posted || ""),
    );
}
function render() {
  const shown = filtered(jobs, tab, {
    employer: $("employer").value,
    role: $("role").value,
    location: $("location").value,
    dismissed: $("dismissed").checked,
  });
  observer?.disconnect();
  $("jobs").querySelectorAll("article").forEach(card => clearTimeout(card.seenTimer));
  $("jobs").replaceChildren();
  $("recommendations").replaceChildren();
  $("count").textContent =
    `${shown.length} ${shown.length === 1 ? "job" : "jobs"} · New opportunities first`;
  const containers = new Map();
  const groups = groupJobs(shown);
  for (const { key, label, open } of catalogueSections) {
    const section = el("details", undefined, "catalogue-section");
    section.open = expanded.get(key) ?? open;
    const summary = el("summary", `${label} · ${groups[key].length}`);
    const chevron = el("span", "⌄", "chevron");
    chevron.setAttribute("aria-hidden", "true");
    summary.append(chevron);
    section.append(summary);
    const cards = el("div", undefined, "jobs");
    if (!groups[key].length) cards.append(el("p", "No jobs in this section.", "muted"));
    section.append(cards);
    section.ontoggle = () => expanded.set(key, section.open);
    $("jobs").append(section);
    for (const job of groups[key]) containers.set(job.id, cards);
  }
  observer = new IntersectionObserver((entries) => {
    for (const entry of entries) {
      clearTimeout(entry.target.seenTimer);
      if (entry.isIntersecting && entry.intersectionRatio >= 0.5) {
        entry.target.seenTimer = setTimeout(async () => {
          const id = entry.target.dataset.jobId;
          if (document.visibilityState !== "visible" || !entry.target.isConnected || observed.has(id)) return;
          observed.add(id);
          try {
            await api(`/jobs/${id}/decision`, { method: "POST", body: JSON.stringify({ action: "seen" }) });
          } catch { observed.delete(id); }
        }, 1000);
      }
    }
  }, { threshold: [0, 0.5] });
  for (const j of shown) {
    const v = j.vacancy,
      card = el("article", undefined, "card");
    card.dataset.jobId = j.id;
    if (!j.seen_at) card.append(el("span", "NEW", "badge"));
    if (v.recommended) card.append(el("span", "TOP PICK", "badge"));
    if (v.vacancy_state === "closed")
      card.append(el("span", "ADVERT CLOSED", "badge"));
    card.append(
      el("span", `${v.match}/100 match`, "score"),
      el("p", v.employer, "company"),
      el("h2", v.title),
      el(
        "p",
        `${v.location} · ${v.distance ?? "Unknown"} km · ${v.job_type || "Unknown"}`,
        "details",
      ),
      el(
        "p",
        `Found ${v.found} · Verified ${v.last_verified || "Unknown"} · ${v.source || "Employer"}${v.hours ? " · " + v.hours : ""}`,
        "muted",
      ),
      el("p", v.why || "Match summary unavailable"),
      el(
        "p",
        v.vacancy_state === "verification_unknown"
          ? "Availability unconfirmed; source check incomplete."
          : "",
        "muted",
      ),
    );
    const links = el("div", undefined, "links");
    const ad = el("a", "View advertisement");
    try {
      const u = new URL(v.url);
      if (["https:", "http:"].includes(u.protocol)) ad.href = u.href;
    } catch {}
    ad.target = "_blank";
    ad.rel = "noopener noreferrer";
    links.append(ad);
    for (const [kind, label] of [
      ["docx", "Word letter"],
      ["md", "Markdown"],
    ])
      if (j.letters?.[kind]) {
        const a = el("a", label);
        a.href = `/api/jobs/${j.id}/letter/${kind}`;
        links.append(a);
      }
    card.append(links);
    const actions = el("div", undefined, "actions");
    for (const [action, label] of [
      [j.saved ? "unsave" : "save", j.saved ? "Unsave" : "Save"],
      [
        j.dismissed ? "restore" : "dismiss",
        j.dismissed ? "Restore" : "Dismiss",
      ],
      ...(j.saved && !j.dismissed ? [["letter", "Create cover letter"]] : []),
      ["applied", j.applied ? "Applied ✓" : "Applied"],
    ]) {
      const b = el("button", label);
      b.disabled = action === "applied" && j.applied;
      b.onclick = async () => {
        if (action === "letter") { openLetterEditor(j); return; }
        b.disabled = true;
        try {
          await api(`/jobs/${j.id}/decision`, {
            method: "POST",
            body: JSON.stringify({ action }),
          });
          await load();
        } catch (e) {
          $("message").textContent = e.message;
          b.disabled = false;
        }
      };
      actions.append(b);
    }
    card.append(actions);
    containers.get(j.id).append(card);
    if (!j.seen_at) observer.observe(card);
    if (v.recommended && !j.dismissed && v.vacancy_state === "open") {
      const pick = el("article", undefined, "card");
      pick.append(
        el("p", v.employer, "company"),
        el("h3", v.title),
        el("p", v.why || "", "muted"),
      );
      $("recommendations").append(pick);
    }
  }
  if (!shown.length)
    $("jobs").append(
      el(
        "p",
        "No jobs in this view. Try another filter or show dismissed jobs.",
        "muted",
      ),
    );
}
async function load() {
  try {
    const previous = new Map(jobs.map(j => [j.id, j.seen_at]));
    jobs = (await api("/jobs")).map(j => previous.has(j.id) ? { ...j, seen_at: previous.get(j.id) } : j);
    try {
      const health = await api("/health");
      const last = health.sync[0]?.last_successful_sync;
      $("health").textContent = syncStatus(last);
    } catch {
      $("health").textContent = "Update time unavailable.";
    }
    $("login").hidden = true;
    $("board").hidden = false;
    $("logout").hidden = false;
    for (const [id, values] of [
      ["employer", jobs.map((j) => j.vacancy.employer)],
      ["role", jobs.map((j) => role(j.vacancy.title))],
      ["location", jobs.map((j) => j.vacancy.location)],
    ]) {
      const select = $(id),
        old = select.value;
      select.replaceChildren(el("option", "All " + id + "s"));
      select.firstChild.value = "";
      for (const text of [...new Set(values)].sort()) {
        const o = el("option", text);
        o.value = text;
        select.append(o);
      }
      select.value = old;
    }
    render();
  } catch (e) {
    if ([401,403].includes(e.status)) clearLetterDrafts();
    $("message").textContent = e.status === 401 ? "" : e.message;
    $("login").hidden = false;
    $("board").hidden = true;
    $("logout").hidden = true;
  }
}
if (typeof document !== "undefined") {
  document.addEventListener("visibilitychange", () => {
    $("jobs").querySelectorAll("article").forEach(card => clearTimeout(card.seenTimer));
    if (document.visibilityState === "visible" && !$("board").hidden) render();
  });
  $("login-form").onsubmit = async (e) => {
    e.preventDefault();
    const button = e.target.querySelector("button");
    button.disabled = true;
    $("message").textContent = "";
    try {
      const form = new FormData(e.target);
      await api("/login", {
        method: "POST",
        body: JSON.stringify(Object.fromEntries(form)),
      });
      e.target.reset();
      await load();
    } catch (error) {
      $("message").textContent = error.message;
    } finally {
      button.disabled = false;
    }
  };
  $("logout").onclick = async () => {
    await api("/logout", { method: "POST" });
    clearLetterDrafts();
    observer?.disconnect();
    observed.clear();
    expanded.clear();
    jobs = [];
    $("jobs").replaceChildren();
    await load();
  };
  document.querySelectorAll("[data-tab]").forEach(
    (b) =>
      (b.onclick = () => {
        tab = b.dataset.tab;
        document
          .querySelectorAll("[data-tab]")
          .forEach((x) => x.setAttribute("aria-pressed", String(x === b)));
        render();
      }),
  );
  for (const id of ["employer", "role", "location", "dismissed"])
    $(id).onchange = render;
  load();
}
