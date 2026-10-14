import test from "node:test";
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { PGlite } from "@electric-sql/pglite";

test("runner without Storage ownership cannot apply unchanged migration 1; transaction rolls back", async () => {
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
  await db.exec("begin;set local role migration_runner");
  await assert.rejects(
    db.exec(sql),
    /must be owner of (?:table|relation) objects/,
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
  await db.close();
});
