import test from "node:test";
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { PGlite } from "@electric-sql/pglite";

test("inspected FMB provisioning triggers execute with synthetic users and retain shared side effects", async () => {
  const db = new PGlite();
  const snapshot = JSON.parse(
    await readFile("tests/fixtures/fmb-provisioning-schema.json", "utf8"),
  );
  await db.exec(
    `create schema auth;create table auth.users(id uuid primary key,email text,raw_user_meta_data jsonb);create type public.app_role as enum ('user');`,
  );
  for (const table of ["profiles", "subscriptions", "user_entitlements"]) {
    const columns = snapshot.dependencies.columns
      .filter((c) => c.table_name === table)
      .map(
        (c) =>
          `${c.column_name} ${c.udt_name === "_text" ? "text[]" : c.udt_name}${c.is_nullable === "NO" ? " not null" : ""}${c.column_default ? " default " + c.column_default : ""}`,
      );
    const constraints = snapshot.dependencies.constraints
      .filter((c) => c.relname === table)
      .map((c) => c.definition);
    await db.exec(
      `create table public.${table}(${[...columns, ...constraints].join(",")})`,
    );
  }
  for (const trigger of snapshot.triggers) {
    await db.exec(trigger.function_definition);
    await db.exec(trigger.definition);
  }
  const user = "11111111-1111-1111-1111-111111111111";
  await db.exec(
    `insert into auth.users values('${user}','synthetic@example.test','{"full_name":"Synthetic User"}')`,
  );
  const profile = (await db.query(`select id,user_id,is_seeded from profiles`))
    .rows[0];
  assert.equal(profile.id, user);
  assert.equal(profile.user_id, null);
  assert.equal(profile.is_seeded, false);
  assert.deepEqual(
    (await db.query("select status,plan from subscriptions")).rows[0],
    { status: "active", plan: "free" },
  );
  assert.equal(
    (await db.query("select deployment_limit from user_entitlements")).rows[0]
      .deployment_limit,
    1,
  );
  await db.close();
});
