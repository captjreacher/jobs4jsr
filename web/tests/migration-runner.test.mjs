import test from "node:test";
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { PGlite } from "@electric-sql/pglite";

test("base migrations execute without Storage ownership; optional policy guard rolls back failure", async () => {
  const db = new PGlite();
  await db.exec(`
 create role anon; create role authenticated; create role migration_runner;
 create role supabase_storage_admin;
 create schema auth;create table auth.users(id uuid primary key);
 create function auth.uid() returns uuid language sql as $$select null::uuid$$;
 create schema storage;
 create table storage.buckets(id text primary key,name text,public boolean,file_size_limit bigint,allowed_mime_types text[]);
 create table storage.objects(name text,bucket_id text);
 alter table storage.objects owner to supabase_storage_admin;
 alter table storage.objects enable row level security;
 create function storage.foldername(text) returns text[] language sql as $$select string_to_array($1,'/')$$;
 grant usage on schema public,auth,storage to migration_runner;
 grant create on schema public to migration_runner;
 grant references on auth.users to migration_runner;
 grant insert,select on storage.buckets to migration_runner;
 grant select,insert,update on storage.objects to migration_runner;
 `);
  const sql = await readFile(
    "supabase/migrations/20261014034534_jobs4jsr_private_board.sql",
    "utf8",
  );
  const health=await readFile('supabase/migrations/20261014041250_jobs4jsr_health.sql','utf8');
  const optional=await readFile('supabase/optional/jobs4jsr_letters_owner_only.sql','utf8');
  await db.exec("begin;set local role migration_runner");
  await assert.rejects(
    db.exec(sql+health+optional),
    /Approved Storage policy owner context required/,
  );
  await db.exec("rollback");
  assert.equal(
    (
      await db.query(
        "select to_regclass('public.jobs4jsr_members') as relation",
      )
    ).rows[0].relation,
    null,
  );
  assert.equal(
    (await db.query("select count(*)::int as count from storage.buckets"))
      .rows[0].count,
    0,
  );
  await db.exec('begin;set local role migration_runner');
  await db.exec(sql+health);await db.exec('commit;reset role');
  for(const name of ['members','jobs','decisions','runs','source_checks','sync_health'])assert.equal((await db.query(`select relrowsecurity from pg_class where oid='public.jobs4jsr_${name}'::regclass`)).rows[0].relrowsecurity,true);
  assert.equal((await db.query("select count(*)::int as count from storage.buckets")).rows[0].count,0);
  assert.equal((await db.query("select pg_get_userbyid(relowner) as owner from pg_class where oid='storage.objects'::regclass")).rows[0].owner,'supabase_storage_admin');
  await db.close();
});
