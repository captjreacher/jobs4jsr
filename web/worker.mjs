export default {
  async fetch(request, env) {
    return handle(request, env).catch(() =>
      reply({ error: "Request failed. Please try again." }, 503),
    );
  },
};
const headers = {
  "Cache-Control": "no-store",
  "X-Content-Type-Options": "nosniff",
  "Referrer-Policy": "no-referrer",
  "Content-Security-Policy":
    "default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'",
};
function reply(body, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { ...headers, "Content-Type": "application/json" },
  });
}
async function upstream(env, path, token, options = {}) {
  return fetch(env.SUPABASE_URL + path, {
    ...options,
    headers: {
      apikey: env.SUPABASE_PUBLISHABLE_KEY,
      Authorization: "Bearer " + token,
      "Content-Type": "application/json",
      ...options.headers,
    },
  });
}
async function identity(env, token) {
  if (!token) return null;
  const r = await upstream(env, "/auth/v1/user", token);
  if (!r.ok) return null;
  const u = await r.json();
  if (u.id !== env.JESS_USER_ID) return null;
  const m = await upstream(
    env,
    `/rest/v1/jobs4jsr_members?user_id=eq.${u.id}&select=user_id,owner_id,kind`,
    token,
  );
  if (!m.ok) return null;
  return (await m.json()).some(
    (x) => x.user_id === u.id && x.owner_id === u.id && x.kind === "reader",
  )
    ? u
    : null;
}
function setCookies(response, t) {
  for (const [name, value, max] of [
    ["access", t.access_token, Math.min(t.expires_in || 3600, 3600)],
    ["refresh", t.refresh_token, 2592000],
  ])
    response.headers.append(
      "Set-Cookie",
      `${name}=${value}; HttpOnly; Secure; SameSite=Strict; Path=/api; Max-Age=${max}`,
    );
  return response;
}
export async function handle(request, env) {
  const url = new URL(request.url),
    path = url.pathname;
  if (url.hostname === "jess.maximisedai.com" && env.LEGACY_REDIRECT_ENABLED === "true") {
    // Never forward credentials, cookies or authentication callback material.
    // Host-only sessions require a fresh login on the canonical hostname.
    if (!["GET", "HEAD"].includes(request.method))
      return reply({ error: "The board has moved. Sign in at https://jess.funkmybrand.com" }, 409);
    const target = new URL("https://jess.funkmybrand.com");
    target.pathname = path;
    const sensitive = /token|code|state|secret|password|jwt|session|authorization|key|signature|ticket/i;
    if (![...url.searchParams].some(([key, value]) => sensitive.test(key) || /^(Bearer\s|eyJ[A-Za-z0-9_-]+\.)/i.test(value)))
      target.search = url.search;
    // Explicit empty fragment prevents browsers inheriting an old OAuth fragment.
    const response = new Response(null, { status: 301, headers: { ...headers, Location: target.href + "#" } });
    for (const name of ["access", "refresh"])
      response.headers.append("Set-Cookie", `${name}=; HttpOnly; Secure; SameSite=Strict; Path=/api; Max-Age=0`);
    return response;
  }
  if (!path.startsWith("/api/")) {
    const r = await env.ASSETS.fetch(request);
    const copy = new Response(r.body, r);
    for (const [k, v] of Object.entries(headers)) copy.headers.set(k, v);
    return copy;
  }
  if (!env.SUPABASE_URL || !env.SUPABASE_PUBLISHABLE_KEY || !env.JESS_USER_ID)
    return reply({ error: "Board is not configured yet." }, 503);
  if (request.method !== "GET" && request.headers.get("Origin") !== url.origin)
    return reply({ error: "Invalid origin" }, 403);
  if (path === "/api/login" && request.method === "POST") {
    const { email, password } = await request.json();
    if (
      typeof email !== "string" ||
      typeof password !== "string" ||
      email.length > 254 ||
      password.length > 256
    )
      return reply({ error: "Invalid credentials" }, 400);
    const r = await upstream(env, "/auth/v1/token?grant_type=password", "", {
      method: "POST",
      body: JSON.stringify({ email, password }),
    });
    if (!r.ok) return reply({ error: "Sign-in unsuccessful" }, 401);
    const tokens = await r.json();
    if (!(await identity(env, tokens.access_token)))
      return reply(
        { error: "This account is not authorised for this board" },
        403,
      );
    return setCookies(reply({ ok: true }), tokens);
  }
  if (path === "/api/logout" && request.method === "POST") {
    const access = (request.headers.get("cookie") || "").match(
      /(?:^|;\s*)access=([^;]+)/,
    )?.[1];
    if (access)
      await upstream(env, "/auth/v1/logout?scope=local", access, {
        method: "POST",
      });
    const response = reply({ ok: true });
    for (const name of ["access", "refresh"])
      response.headers.append(
        "Set-Cookie",
        `${name}=; HttpOnly; Secure; SameSite=Strict; Path=/api; Max-Age=0`,
      );
    return response;
  }
  const cookie = Object.fromEntries(
    (request.headers.get("cookie") || "")
      .split(";")
      .map((x) => x.trim().split("=")),
  );
  let token = cookie.access,
    tokens = null,
    user = await identity(env, token);
  if (!user && cookie.refresh) {
    const r = await upstream(
      env,
      "/auth/v1/token?grant_type=refresh_token",
      "",
      {
        method: "POST",
        body: JSON.stringify({ refresh_token: cookie.refresh }),
      },
    );
    if (r.ok) {
      tokens = await r.json();
      token = tokens.access_token;
      user = await identity(env, token);
    }
  }
  if (!user) return reply({ error: "Please sign in" }, 401);
  let result;
  if (path === "/api/health" && request.method === "GET") {
    const sync = await upstream(
        env,
        "/rest/v1/jobs4jsr_sync_health?select=*",
        token,
      ),
      checks = await upstream(
        env,
        "/rest/v1/jobs4jsr_source_checks?select=source,payload&order=run_id.desc&limit=100",
        token,
      );
    if (!sync.ok || !checks.ok)
      return reply({ error: "Health unavailable" }, 503);
    result = reply({ sync: await sync.json(), sources: await checks.json() });
  } else if (path === "/api/jobs" && request.method === "GET") {
    const jobs = await upstream(env, "/rest/v1/jobs4jsr_jobs?select=*", token),
      decisions = await upstream(
        env,
        "/rest/v1/jobs4jsr_decisions?select=*",
        token,
      );
    if (!jobs.ok || !decisions.ok)
      return reply({ error: "Catalogue unavailable" }, 503);
    const states = new Map((await decisions.json()).map((x) => [x.job_id, x]));
    result = reply(
      (await jobs.json()).map((x) => ({
        ...x,
        applied: x.vacancy.legacy_application_status === "Applied",
        ...states.get(x.id),
      })),
    );
  } else if (
    /^\/api\/jobs\/[a-f0-9-]{36}\/decision$/.test(path) &&
    request.method === "POST"
  ) {
    const id = path.split("/")[3],
      body = await request.json(),
      actions = {
        seen: ["seen_at", new Date().toISOString()],
        save: ["saved", true],
        unsave: ["saved", false],
        dismiss: ["dismissed", true],
        restore: ["dismissed", false],
        applied: ["applied", true],
      };
    if (!actions[body.action]) return reply({ error: "Invalid action" }, 400);
    const [field, value] = actions[body.action];
    // PATCH only the chosen flag, avoiding lost updates to other decisions.
    const jobResponse = await upstream(
      env,
      `/rest/v1/jobs4jsr_jobs?id=eq.${id}&select=vacancy`,
      token,
    );
    if (!jobResponse.ok) return reply({ error: "Job unavailable" }, 503);
    const job = (await jobResponse.json())[0];
    if (!job) return reply({ error: "Job unavailable" }, 404);
    const initial = {
      job_id: id,
      owner_id: user.id,
      saved: false,
      dismissed: false,
      applied: job.vacancy.legacy_application_status === "Applied",
    };
    let r = await upstream(
      env,
      "/rest/v1/jobs4jsr_decisions?on_conflict=job_id",
      token,
      {
        method: "POST",
        headers: { Prefer: "resolution=ignore-duplicates" },
        body: JSON.stringify(initial),
      },
    );
    if (r.ok)
      r = await upstream(
        env,
        `/rest/v1/jobs4jsr_decisions?job_id=eq.${id}${field === "seen_at" ? "&seen_at=is.null" : ""}`,
        token,
        { method: "PATCH", body: JSON.stringify({ [field]: value }) },
      );
    result = reply(
      r.ok ? { ok: true } : { error: "Could not save decision" },
      r.ok ? 200 : 403,
    );
  } else if (
    /^\/api\/jobs\/[a-f0-9-]{36}\/letter\/(docx|md)$/.test(path) &&
    request.method === "GET"
  ) {
    const id = path.split("/")[3],
      kind = path.split("/")[5];
    const r = await upstream(
      env,
      `/rest/v1/jobs4jsr_jobs?id=eq.${id}&select=letters,owner_id`,
      token,
    );
    if (!r.ok) return reply({ error: "Unavailable" }, 404);
    const job = (await r.json())[0],
      key = job?.letters?.[kind];
    if (
      !key ||
      job.owner_id !== user.id ||
      !key.startsWith(user.id + "/" + id + "/")
    )
      return reply({ error: "Letter not found" }, 404);
    const file = await upstream(
      env,
      "/storage/v1/object/authenticated/jobs4jsr-letters/" + key,
      token,
    );
    if (!file.ok) return reply({ error: "Letter unavailable" }, 404);
    result = new Response(file.body, {
      headers: {
        ...headers,
        "Content-Type":
          kind === "docx"
            ? "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            : "text/markdown; charset=utf-8",
        "Content-Disposition": `attachment; filename="Suggested_Cover_Letter.${kind}"`,
      },
    });
  } else result = reply({ error: "Not found" }, 404);
  return tokens ? setCookies(result, tokens) : result;
}
