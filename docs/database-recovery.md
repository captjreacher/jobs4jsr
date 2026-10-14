# Shared Funk My Brand recovery procedure

Status on 14 October 2026: **NOT VERIFIED**. This is a prepared procedure, not evidence of an existing restorable backup. No production dump or restore was executed. Project: `qnvihygrnfgpmsznayje`, PostgreSQL 17.6.1.021.

## Existing facilities and blockers

The existing Supabase CLI credential in Windows Credential Manager can read the Management API. The backup endpoint returned HTTP 200 with `walg_enabled=true`, `pitr_enabled=false`, `backups=[]`, and empty `physical_backup_data`. No recovery timestamp, retention or usable restore target is evidenced. WAL support alone proves neither backup existence nor recovery capability. A managed restore must be confirmed with Supabase; restoring the shared project can roll back unrelated FMB customers, CVs and services.

Existing CLI 2.109.1 establishes its approved temporary database connection without a new persistent credential. There is no locally configured persistent database password. Native PostgreSQL clients were not found; Docker Desktop is installed but its Linux engine pipe is unavailable, its service is stopped and the hidden desktop launch did not establish an engine. No restore-capable local runtime was verified. Do not publish a schema-only dump as a full backup.

## Required scope

A consistent database archive must contain schema **and populated data**, including `public`, `auth`, `storage`, `supabase_migrations`, `realtime`, `extensions`, `graphql`, `graphql_public` and `vault`, where the approved administrator is permitted to read them. Capture object ownership, grants/default grants, RLS enable/force flags and policy definitions, triggers/functions, extension versions and migration history. Capture role definitions and membership separately; passwords must not be exported to a review document. Include Auth identities/users and Storage bucket/object metadata. Do not assume the CLI default public-only dump includes managed schemas.

Capture all database schemas in one PostgreSQL 17 custom-format `pg_dump`, using one connection/snapshot. Explicitly inspect omitted/inaccessible objects. Role metadata is a separate operation: freeze role/schema changes during capture and record timestamps; it is not part of the data snapshot. Preserve copies of existing managed role definitions without blindly recreating platform roles on Supabase.

## Repeatable capture (prepared, not executed)

Use the existing approved administrative connection, with libpq connection/credential information supplied privately in process environment or an owner-managed service file. Never paste connection strings, use shell tracing or save CLI dry-run output containing credentials. Before capture verify the selected connection maps to this exact project (compare host to its linked reference), current user/privileges and server version. `PGSERVICE` below is a placeholder for that approved connection, not an existing configured service or permission to create credentials.

```powershell
$ErrorActionPreference='Stop'
function Invoke-PG { param([string]$Tool,[string[]]$Arguments)
  & $Tool @Arguments
  if ($LASTEXITCODE -ne 0) { throw "$Tool failed; stop" }
}
# Owner supplies existing approved libpq connection privately; verify project first.
if (-not $env:PGSERVICE) { throw 'Approved connection is not configured' }
$recoveryDir='C:\DEV_LOCAL\jobs4jsr\tmp\recovery\pre-jobs4jsr'
New-Item -ItemType Directory -Force -Path $recoveryDir | Out-Null
Invoke-PG pg_dump @('--format=custom','--verbose',"--file=$recoveryDir\database.dump")
Invoke-PG pg_dumpall @('--roles-only','--no-role-passwords',"--file=$recoveryDir\roles.sql")
Invoke-PG pg_restore @('--list',"$recoveryDir\database.dump")
Get-FileHash "$recoveryDir\database.dump","$recoveryDir\roles.sql" |
  Export-Csv "$recoveryDir\checksums.csv" -NoTypeInformation
```

Protect the directory with an owner-only ACL before capturing personal data. Keep it ignored, encrypt any retained copy using an existing approved facility, and store a separate protected copy outside this checkout. Record tool versions, project identity, snapshot time, all stderr warnings, checksums, archive object inventory and role membership. A permission failure or incomplete managed-schema archive means capture is NOT VERIFIED. Do not fix it by granting application users administrative privileges.

## Isolated restoration gate

Use an existing free isolated PostgreSQL 17/Supabase-compatible runtime. Never point restore commands at production. Match extensions and managed schema dependencies first; vanilla PostgreSQL may not support Supabase Vault or platform roles. Inspect role SQL and prepare only required local roles, retaining the original capture. No automatic production role replay.

With a privately configured **local-only** libpq connection, verify server address is loopback and database is a disposable test database before running:

```powershell
# Separately select and verify the isolated connection; do not reuse production PGSERVICE.
if ($env:PGSERVICE -ne 'jobs4jsr_isolated_restore') { throw 'Select verified local restore service' }
Invoke-PG pg_restore @('--exit-on-error','--single-transaction','--dbname=jobs4jsr_restore',"$recoveryDir\database.dump")
```

Do not use `--no-owner` or `--no-acl` to claim ownership/security parity. Resolve local role/extension incompatibilities explicitly and report them. Compare every application table's row count and stable content digest against the snapshot, Auth identities, Storage metadata, migration versions, functions/triggers, owners, ACL/default grants and RLS/policies. Exercise anon/unrelated-user denial, authorised access and existing CV/Auth behaviour. Then apply both Jobs4JSR migrations in order in this restored database; verify security and failure rollback. Record duration and evidence. Archive existence or `pg_restore --list` alone is insufficient. This gate is currently **unexecuted**.

## Recovery limitations and owner decisions

Database dumps do not contain Storage object bytes, Edge Function code/configuration/secrets, external OAuth secrets, Cloudflare configuration, delivery/mail state or local SQLite/letters. Vault encrypted values may be unusable without platform encryption keys. Auth recovery depends on the original signing/encryption configuration. Role passwords are deliberately excluded. Inventory private Storage objects and back up their bytes/checksums using an approved separate process before claiming full-project recovery. No such object backup has been verified here.

Recovering only new empty Jobs4JSR tables is an additive cleanup, not restoration of FMB. Production full-project restoration requires owner acceptance of shared-project impact and a provider-supported procedure; never trial it in production. If the local runtime cannot be restored, request approval for a specifically scoped non-production Supabase restore test and its quoted cost before creating a project. A backup/restore approval does not approve migrations or activation.
