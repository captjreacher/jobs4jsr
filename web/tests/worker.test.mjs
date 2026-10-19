import test from "node:test";
import assert from "node:assert/strict";
import { handle } from "../worker.mjs";
import { filtered } from "../public/app.js";
const user = "11111111-1111-1111-1111-111111111111",
  id = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa";
const env = {
  SUPABASE_URL: "https://example.supabase.co",
  SUPABASE_PUBLISHABLE_KEY: "publishable-test",
  JESS_USER_ID: user,
};
function req(path, method = "GET", body, extra = {}) {
  return new Request("https://jess.test/api" + path, {
    method,
    headers: { Origin: "https://jess.test", Cookie: "access=valid", ...extra },
    body: body ? JSON.stringify(body) : undefined,
  });
}
const membership = [{ user_id: user, owner_id: user, kind: "reader" }];
const json = (body, status = 200) =>
  new Response(JSON.stringify(body), { status });
test("unauthenticated API and letters rejected", async () => {
  const old = global.fetch;
  global.fetch = async () => json({}, 401);
  try {
    assert.equal(
      (await handle(req("/jobs", "GET", null, { Cookie: "" }), env)).status,
      401,
    );
    assert.equal(
      (
        await handle(
          req(`/jobs/${id}/letter/docx`, "GET", null, { Cookie: "" }),
          env,
        )
      ).status,
      401,
    );
  } finally {
    global.fetch = old;
  }
});
test("wrong user rejected; CSRF rejected before upstream", async () => {
  const old = global.fetch;
  global.fetch = async () => json({ id: "other-user" });
  try {
    assert.equal((await handle(req("/jobs"), env)).status, 401);
    assert.equal(
      (
        await handle(
          req(
            `/jobs/${id}/decision`,
            "POST",
            { action: "save" },
            { Origin: "https://evil.test" },
          ),
          env,
        )
      ).status,
      403,
    );
  } finally {
    global.fetch = old;
  }
});
test("login cookies private and token absent from response", async () => {
  const old = global.fetch;
  global.fetch = async (url) =>
    url.includes("jobs4jsr_members")
      ? json(membership)
      : url.includes("/token")
        ? json({
            access_token: "secret-token",
            refresh_token: "refresh-token",
            expires_in: 3600,
          })
        : json({ id: user });
  try {
    const r = await handle(
      req("/login", "POST", {
        email: "fictional@example.test",
        password: "test",
      }),
      env,
    );
    assert.equal(r.status, 200);
    assert.match(r.headers.get("set-cookie"), /HttpOnly/);
    assert.match(r.headers.get("set-cookie"), /Secure/);
    assert.match(r.headers.get("set-cookie"), /SameSite=Strict/);
    assert.equal(await r.text(), '{"ok":true}');
  } finally {
    global.fetch = old;
  }
});
test("decision patch changes one flag only and restore is supported", async () => {
  const old = global.fetch;
  const writes = [];
  global.fetch = async (url, options) => {
    if (url.includes("jobs4jsr_members")) return json(membership);
    if (url.includes("/auth/")) return json({ id: user });
    if (url.includes("jobs4jsr_jobs"))
      return json([{ vacancy: { legacy_application_status: "Applied" } }]);
    writes.push(options);
    return new Response(null, { status: 204 });
  };
  try {
    assert.equal(
      (
        await handle(
          req(`/jobs/${id}/decision`, "POST", { action: "restore" }),
          env,
        )
      ).status,
      200,
    );
    assert.deepEqual(JSON.parse(writes[1].body), { dismissed: false });
    assert.equal(writes[1].method, "PATCH");
    assert.equal(JSON.parse(writes[0].body).applied, true);
  } finally {
    global.fetch = old;
  }
});
test("private letter enforces owner and sends no public URL", async () => {
  const old = global.fetch;
  global.fetch = async (url) =>
    url.includes("jobs4jsr_members")
      ? json(membership)
      : url.includes("/auth/")
        ? json({ id: user })
        : url.includes("/rest/")
          ? json([
              {
                owner_id: "other",
                letters: { docx: `${user}/${id}/doc.docx` },
              },
            ])
          : json({});
  try {
    assert.equal(
      (await handle(req(`/jobs/${id}/letter/docx`), env)).status,
      404,
    );
  } finally {
    global.fetch = old;
  }
});
test("sorting, saved/applied and dismissed restoration views", () => {
  const rows = [
    {
      id: "a",
      dismissed: true,
      vacancy: { is_new: true, match: 100, title: "Waiter" },
    },
    {
      id: "b",
      saved: true,
      vacancy: { is_new: false, match: 100, title: "Cafe Assistant" },
    },
    {
      id: "c",
      applied: true,
      vacancy: { is_new: true, match: 70, title: "Waiter" },
    },
  ];
  assert.deepEqual(
    filtered(rows, "all").map((j) => j.id),
    ["c", "b"],
  );
  assert.equal(filtered(rows, "saved").length, 1);
  assert.equal(filtered(rows, "applied").length, 1);
  assert.equal(filtered(rows, "all", { dismissed: true }).length, 3);
});

test("revoked membership denied even for configured owner", async () => {
  const old = global.fetch;
  global.fetch = async (url) =>
    url.includes("/auth/") ? json({ id: user }) : json([]);
  try {
    assert.equal((await handle(req("/jobs"), env)).status, 401);
  } finally {
    global.fetch = old;
  }
});
test("dismissed tab contains only dismissed jobs", () => {
  assert.deepEqual(
    filtered(
      [
        { id: "a", dismissed: true, vacancy: { title: "Waiter" } },
        { id: "b", vacancy: { title: "Waiter" } },
      ],
      "dismissed",
    ).map((j) => j.id),
    ["a"],
  );
});

test("authorised private letter download uses authenticated Storage", async () => {
  const old = global.fetch;
  const calls = [];
  global.fetch = async (url) => {
    calls.push(url);
    if (url.includes("jobs4jsr_members")) return json(membership);
    if (url.includes("/auth/")) return json({ id: user });
    if (url.includes("/rest/"))
      return json([
        { owner_id: user, letters: { md: `${user}/${id}/hash.md` } },
      ]);
    return new Response("Fictional letter");
  };
  try {
    const r = await handle(req(`/jobs/${id}/letter/md`), env);
    assert.equal(r.status, 200);
    assert.equal(await r.text(), "Fictional letter");
    assert.match(r.headers.get("Content-Disposition"), /attachment/);
    assert.equal(r.headers.get("Cache-Control"), "no-store");
    assert.ok(
      calls.some((u) => u.includes("/object/authenticated/jobs4jsr-letters/")),
    );
  } finally {
    global.fetch = old;
  }
});

test("expired access refreshes and revalidates membership before serving jobs", async () => {
  const old = global.fetch;
  global.fetch = async (url, options) => {
    if (url.includes("/token"))
      return json({
        access_token: "fresh",
        refresh_token: "rotated",
        expires_in: 3600,
      });
    if (url.includes("/auth/"))
      return options.headers.Authorization === "Bearer fresh"
        ? json({ id: user })
        : json({}, 401);
    if (url.includes("jobs4jsr_members")) return json(membership);
    return json([]);
  };
  try {
    const r = await handle(
      req("/jobs", "GET", null, {
        Cookie: "access=expired; refresh=valid-refresh",
      }),
      env,
    );
    assert.equal(r.status, 200);
    assert.match(r.headers.get("Set-Cookie"), /refresh=rotated/);
  } finally {
    global.fetch = old;
  }
});

test("seen records server time once, without changing Saved/Applied/Dismissed", async () => {
  const old = global.fetch;
  const writes = [];
  global.fetch = async (url, options) => {
    if (url.includes("jobs4jsr_members")) return json(membership);
    if (url.includes("/auth/")) return json({ id: user });
    if (url.includes("jobs4jsr_jobs")) return json([{vacancy:{}}]);
    writes.push({url,...options});
    return new Response(null,{status:204});
  };
  try {
    const before = Date.now();
    assert.equal((await handle(req(`/jobs/${id}/decision`, "POST", {action:"seen",seen_at:"forged"}),env)).status,200);
    assert.match(writes[1].url,/&seen_at=is.null$/);
    const patch = JSON.parse(writes[1].body);
    assert.deepEqual(Object.keys(patch),["seen_at"]);
    assert.ok(Date.parse(patch.seen_at)>=before && Date.parse(patch.seen_at)<=Date.now());
    assert.equal(writes[0].headers.Prefer,"resolution=ignore-duplicates");
  } finally { global.fetch=old; }
});
