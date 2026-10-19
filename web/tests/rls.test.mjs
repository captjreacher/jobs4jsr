import test from "node:test";
import assert from "node:assert/strict";
import { readFile, readdir } from "node:fs/promises";
import { PGlite } from "@electric-sql/pglite";
test("real PostgreSQL RLS separates reader, sync, uninvited users and letters", async () => {
  const db = new PGlite();
  await db.exec(
    `create role anon;create role authenticated;create schema auth;create table auth.users(id uuid primary key);create function auth.uid() returns uuid language sql stable as $$select nullif(current_setting('request.jwt.claim.sub',true),'')::uuid$$;grant usage on schema auth to authenticated;grant execute on function auth.uid() to authenticated;create schema storage;create table storage.buckets(id text primary key,name text,public boolean,file_size_limit bigint,allowed_mime_types text[]);create table storage.objects(id serial,name text,bucket_id text);alter table storage.objects enable row level security;grant usage on schema storage to authenticated;grant select,insert,update on storage.objects to authenticated;grant usage on sequence storage.objects_id_seq to authenticated;create function storage.foldername(text) returns text[] language sql immutable as $$select string_to_array($1,'/')$$;grant execute on function storage.foldername(text) to authenticated;`,
  );
  await db.exec(
    `alter default privileges in schema public grant all on tables to anon,authenticated,public;grant usage on schema storage to anon;grant select on storage.objects to anon;`,
  );
  const file = (await readdir("supabase/migrations")).find((x) =>
    x.endsWith("_jobs4jsr_private_board.sql"),
  );
  for (const migration of (await readdir("supabase/migrations"))
    .filter((x) => x.endsWith(".sql"))
    .sort())
    await db.exec(await readFile("supabase/migrations/" + migration, "utf8"));
  for (const table of [
    "members",
    "jobs",
    "decisions",
    "runs",
    "source_checks",
    "sync_health",
  ]) {
    assert.equal(
      (
        await db.query(
          `select relrowsecurity from pg_class where oid='public.jobs4jsr_${table}'::regclass`,
        )
      ).rows[0].relrowsecurity,
      true,
    );
    for (const permission of [
      "SELECT",
      "INSERT",
      "UPDATE",
      "DELETE",
      "TRUNCATE",
    ])
      assert.equal(
        (
          await db.query(
            `select has_table_privilege('anon','public.jobs4jsr_${table}','${permission}') as allowed`,
          )
        ).rows[0].allowed,
        false,
      );
    for (const permission of ["DELETE", "TRUNCATE"])
      assert.equal(
        (
          await db.query(
            `select has_table_privilege('authenticated','public.jobs4jsr_${table}','${permission}') as allowed`,
          )
        ).rows[0].allowed,
        false,
      );
  }
  await db.exec(await readFile("supabase/optional/jobs4jsr_seen_review.sql", "utf8"));
  // Hosted letters are an optional owner-only enhancement, never a base-migration side effect.
  assert.equal((await db.query("select count(*)::int as count from storage.buckets where id='jobs4jsr-letters'")).rows[0].count,0);
  await db.exec(await readFile('supabase/optional/jobs4jsr_letters_owner_only.sql','utf8'));
  const owner = "11111111-1111-1111-1111-111111111111",
    sync = "22222222-2222-2222-2222-222222222222",
    stranger = "33333333-3333-3333-3333-333333333333",
    job = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa";
  await db.exec(
    `insert into auth.users values('${owner}'),('${sync}'),('${stranger}');insert into jobs4jsr_members values('${owner}','${owner}','reader'),('${sync}','${owner}','sync');insert into jobs4jsr_jobs values('${job}','${owner}','{"title":"Fictional Waiter"}','{}');insert into storage.objects(name,bucket_id) values('${owner}/${job}/letter.docx','jobs4jsr-letters');set role authenticated;select set_config('request.jwt.claim.sub','${stranger}',false);`,
  );
  assert.equal((await db.query("select * from jobs4jsr_jobs")).rows.length, 0);
  assert.equal(
    (await db.query("select * from storage.objects")).rows.length,
    0,
  );
  assert.equal(
    (await db.query("select * from jobs4jsr_sync_health")).rows.length,
    0,
  );
  await assert.rejects(
    db.exec(
      `insert into jobs4jsr_members values('${stranger}','${owner}','sync')`,
    ),
  );
  await assert.rejects(
    db.exec(
      `insert into storage.objects(name,bucket_id) values('${owner}/forged.docx','jobs4jsr-letters')`,
    ),
  );
  await db.exec(`select set_config('request.jwt.claim.sub','${owner}',false)`);
  assert.equal((await db.query("select * from jobs4jsr_jobs")).rows.length, 1);
  assert.equal(
    (await db.query("select * from storage.objects")).rows.length,
    1,
  );
  await db.exec(
    `insert into jobs4jsr_decisions(job_id,owner_id,saved,dismissed,applied) values('${job}','${owner}',true,true,true)`,
  );
  assert.equal(
    (await db.query("update jobs4jsr_jobs set vacancy='{}' returning *")).rows
      .length,
    0,
  );
  await db.exec(`select set_config('request.jwt.claim.sub','${sync}',false)`);
  await db.exec(
    `insert into jobs4jsr_sync_health values('${owner}',now());insert into storage.objects(name,bucket_id) values('${owner}/${job}/second.docx','jobs4jsr-letters')`,
  );
  await assert.rejects(
    db.exec(
      `insert into storage.objects(name,bucket_id) values('${stranger}/forged.docx','jobs4jsr-letters')`,
    ),
  );
  await assert.rejects(
    db.exec(
      `insert into jobs4jsr_decisions(job_id,owner_id,saved,dismissed,applied) values('${job}','${owner}',false,false,false) on conflict(job_id) do update set saved=false`,
    ),
  );
  await db.exec(
    `update jobs4jsr_jobs set vacancy='{"title":"Updated vacancy"}' where id='${job}'`,
  );
  assert.equal(
    (await db.query("select * from jobs4jsr_decisions")).rows.length,
    0,
  );
  await db.exec(`select set_config('request.jwt.claim.sub','${owner}',false)`);
  const decision = (await db.query("select * from jobs4jsr_decisions")).rows[0];
  assert.ok(decision.saved && decision.dismissed && decision.applied);
  assert.equal(decision.seen_at, null);
  await db.exec(`update jobs4jsr_decisions set seen_at=now() where seen_at is null`);
  assert.ok((await db.query("select seen_at from jobs4jsr_decisions")).rows[0].seen_at);
  await db.exec(`update jobs4jsr_decisions set dismissed=false`);
  assert.equal(
    (await db.query("select dismissed from jobs4jsr_decisions")).rows[0]
      .dismissed,
    false,
  );
  await db.exec("reset role;set role anon");
  await assert.rejects(db.query("select * from jobs4jsr_jobs"));
  await assert.rejects(db.query("select * from jobs4jsr_sync_health"));
  assert.equal(
    (await db.query("select * from storage.objects")).rows.length,
    0,
  );
  await db.exec("reset role");
  assert.equal(
    (await db.query("select public from storage.buckets")).rows[0].public,
    false,
  );
  await db.close();
});
