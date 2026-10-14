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
  $("jobs").replaceChildren();
  $("recommendations").replaceChildren();
  $("count").textContent =
    `${shown.length} ${shown.length === 1 ? "job" : "jobs"} · New opportunities first`;
  for (const j of shown) {
    const v = j.vacancy,
      card = el("article", undefined, "card");
    if (v.is_new) card.append(el("span", "NEW", "badge"));
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
      ["applied", j.applied ? "Applied ✓" : "Applied"],
    ]) {
      const b = el("button", label);
      b.disabled = action === "applied" && j.applied;
      b.onclick = async () => {
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
    $("jobs").append(card);
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
    jobs = await api("/jobs");
    try {
      const health = await api("/health");
      const last = health.sync[0]?.last_successful_sync;
      const latest = new Map();
      for (const row of health.sources.sort((a, b) =>
        (b.payload.checked_at || "").localeCompare(a.payload.checked_at || ""),
      )) {
        if (!latest.has(row.source)) latest.set(row.source, row.payload);
      }
      const failed = [...latest]
        .filter(([, check]) => check.status !== "success")
        .map(([name]) => name);
      $("health").textContent =
        (last
          ? `Last synchronised ${last}. Results remain available while the discovery PC is offline.`
          : "Not yet synchronised.") +
        (failed.length ? ` Checks incomplete: ${failed.join(", ")}.` : "");
    } catch {
      $("health").textContent = "Synchronisation health unavailable.";
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
    $("message").textContent = e.status === 401 ? "" : e.message;
    $("login").hidden = false;
    $("board").hidden = true;
    $("logout").hidden = true;
  }
}
if (typeof document !== "undefined") {
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
