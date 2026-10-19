import test from "node:test";
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { PGlite } from "@electric-sql/pglite";

test("seen migration preserves existing data and RLS; first timestamp survives repeat writes and decisions", async () => {
  const db = new PGlite();
  try {
    const owner = "11111111-1111-1111-1111-111111111111";
    const sync = "22222222-2222-2222-2222-222222222222";
    const stranger = "33333333-3333-3333-3333-333333333333";
    const job = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa";
    await db.exec(`create role anon; create role authenticated; create schema auth;
      create table auth.users(id uuid primary key);
      create function auth.uid() returns uuid language sql stable as $$select nullif(current_setting('request.jwt.claim.sub',true),'')::uuid$$;
      grant usage on schema auth to authenticated; grant execute on function auth.uid() to authenticated;`);
    await db.exec(await readFile("supabase/migrations/20261014034534_jobs4jsr_private_board.sql", "utf8"));
    await db.exec(`insert into auth.users values('${owner}'),('${sync}'),('${stranger}');
      insert into jobs4jsr_members values('${owner}','${owner}','reader'),('${sync}','${owner}','sync');
      insert into jobs4jsr_jobs values('${job}','${owner}','{"found":"2026-10-14"}','{}');
      insert into jobs4jsr_decisions values('${job}','${owner}',true,true,true);`);
    const policies = (await db.query("select * from pg_policies where tablename='jobs4jsr_decisions' order by policyname")).rows;
    const jobsBefore = (await db.query("select * from jobs4jsr_jobs")).rows;
    const flagsBefore = (await db.query("select job_id,owner_id,saved,dismissed,applied from jobs4jsr_decisions")).rows;
    await db.exec(await readFile("supabase/optional/jobs4jsr_seen_review.sql", "utf8"));
    assert.deepEqual((await db.query("select * from jobs4jsr_jobs")).rows, jobsBefore);
    assert.deepEqual((await db.query("select job_id,owner_id,saved,dismissed,applied from jobs4jsr_decisions")).rows, flagsBefore);
    assert.equal((await db.query("select seen_at from jobs4jsr_decisions")).rows[0].seen_at, null);
    assert.deepEqual((await db.query("select * from pg_policies where tablename='jobs4jsr_decisions' order by policyname")).rows, policies);
    assert.equal((await db.query("select relrowsecurity from pg_class where oid='jobs4jsr_decisions'::regclass")).rows[0].relrowsecurity, true);

    await db.exec("set role authenticated");
    for (const user of [sync, stranger]) {
      await db.exec(`select set_config('request.jwt.claim.sub','${user}',false)`);
      assert.equal((await db.query("select * from jobs4jsr_decisions")).rows.length, 0);
      assert.equal((await db.query("update jobs4jsr_decisions set seen_at=now() returning *")).rows.length, 0);
      await assert.rejects(db.exec(`insert into jobs4jsr_decisions(job_id,owner_id,seen_at) values('${job}','${owner}',now())`));
    }
    await db.exec(`select set_config('request.jwt.claim.sub','${owner}',false)`);
    await db.exec("update jobs4jsr_decisions set seen_at='2026-10-19T00:00:00Z' where seen_at is null");
    await db.exec("update jobs4jsr_decisions set seen_at='2026-10-20T00:00:00Z' where seen_at is null");
    assert.deepEqual((await db.query("select job_id,owner_id,saved,dismissed,applied from jobs4jsr_decisions")).rows, flagsBefore);
    await db.exec("update jobs4jsr_decisions set saved=false; update jobs4jsr_decisions set dismissed=false");
    const state = (await db.query("select * from jobs4jsr_decisions")).rows[0];
    assert.equal(new Date(state.seen_at).toISOString(), "2026-10-19T00:00:00.000Z");
    assert.equal(state.applied, true);
    await assert.rejects(db.exec(`update jobs4jsr_decisions set owner_id='${stranger}'`));
    await db.exec("reset role; set role anon");
    await assert.rejects(db.query("select seen_at from jobs4jsr_decisions"));
    await assert.rejects(db.exec("update jobs4jsr_decisions set seen_at=now()"));
  } finally { await db.close(); }
});
