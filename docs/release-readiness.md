# Jobs4JSR controlled release readiness

Prepared 14 October 2026, Pacific/Auckland. Scope: private vacancy board with Save, Dismiss and Applied. **Production activation is not authorised or performed.** Hosted letters and cloud discovery remain separate enhancements.

## Merge and installation

[PR #3](https://github.com/captjreacher/jobs4jsr/pull/3) was already merged at 17:40:01 NZDT (04:40:01 UTC) when inspected. Merge commit: `ebc8674c11b8e18db0b9954859c06510b59724b9`; reviewed implementation head: `7d6442477f330ce42883152ef2cacd866870dcc8`. GitGuardian completed successfully. GitHub reports main is not protected and there are no repository rulesets, so no enforced required-check gate was found. No additional merge was performed.

The original checkout `C:\DEV_LOCAL\jobs4jsr` is on main and fast-forwarded to that merge commit. Earlier drafts were preserved as named local stash `Preserved pre-release private-board drafts 2026-10-14`, object `c2c2efae60ab890687a3d0cb898e3a62d42664f8`. It was not reapplied over released code. To inspect it use `git stash show --include-untracked --stat c2c2efae60ab890687a3d0cb898e3a62d42664f8`. For recovery, create a separate worktree on `codex/private-job-board`, then apply that object there; do not apply it over main or drop the stash before reviewing recovery.

Local dependencies installed from the lockfile. Fresh validation in the original checkout: **41 Python tests and 11 Node/PostgreSQL tests pass**; Worker packaging passes. CLI setup succeeds. The local private `.env` contains only `JOBS4JSR_LETTER_UPLOAD_APPROVED=false`; no sync URL or credentials are configured. No production publication can occur from this configuration. Keep that flag false throughout the vacancy-board release.

Preservation verification: 27 recorded private documents/profile/letter files have unchanged SHA256 hashes. All rows in SQLite `jobs`, `runs` and `status_history` match the pre-update backup. Backup: ignored `tmp/release-readiness/history-before.sqlite3`; hashes: ignored `tmp/release-readiness/private-hashes.json`. Existing 11-vacancy catalogue and reports remain local; no discovery was triggered for this release preparation.

Windows task `Jobs4JSR Discovery` has identical exported XML before/after, last result 0, next execution **Friday 16 October 2026 09:00 NZ local time**. Monday/Wednesday/Friday timing, local PC/sign-in dependency and latest-slot catch-up remain unchanged. No cloud schedule is added.

## Supabase review

Target only Funk My Brand `qnvihygrnfgpmsznayje`. Read-only production metadata shows no `jobs4jsr_*` tables and no `jobs4jsr-letters` bucket, so no name collision was observed. Production RLS/grants for these new objects cannot be verified until approved migration; the current evidence is migration review plus local PostgreSQL tests.

| Migration | Proposed changes | Review outcome |
|---|---|---|
| `20261014034534_jobs4jsr_private_board.sql` | Membership, vacancy/source-alias projection, independent decisions, private letter metadata/bucket and policies | RLS enabled at creation; PUBLIC/anon grants revoked; authenticated gets explicit SELECT and necessary writes, with owner/member policies restricting rows. Membership cannot be self-granted. Reader must equal owner; publisher can write assigned-owner facts but not decisions. Composite FK enforces job/decision ownership. Empty private bucket would be created, but no letter upload is part of release. |
| `20261014041250_jobs4jsr_health.sql` | Discovery runs/source checks and last sync | Same grant/RLS separation; run-owner FK prevents mismatched source checks; only assigned publisher can update health. |

No DELETE/TRUNCATE grants or definer RPCs are introduced. Existing production Storage policies are explicitly limited to `logos` or `uploads`; no inspected blanket policy grants access to the proposed new bucket. The proposed bucket is private, with owner-folder access and publisher-only INSERT/UPDATE. No service-role key is used by the app/publisher. Worker also checks current Auth identity and live Jobs4JSR reader membership, so existing FMB users are not automatically admitted. Authorisation does not trust user-editable metadata.

Local PGlite tests apply both migrations and exercise effective table grants, real RLS, unrelated-user denial, reader/publisher separation, decision retention and private Storage path restrictions using Auth/Storage stubs. They do not certify PostgREST schema exposure, real JWTs, Supabase Storage API, production inherited privileges or Auth provider settings. No new board-specific blocker was observed in the inspected code/migrations, but those integration gates remain outstanding.

### Existing Auth and CV compatibility

The Jobs4JSR migrations do not modify any existing CV table, grant, policy, Auth function or trigger. Production Auth user INSERT invokes three existing triggers: `handle_new_user` creates a `profiles` row with id/email/full_name; `handle_new_user_subscription` creates an active/free subscription; `seed_user_entitlement` creates a free entitlement with deployment_limit 1. Reviewed column defaults/nullability support these inserts, but actual account provisioning was not performed. New Jess/machine users therefore have **shared FMB side effects**, not just board membership. Reusing a verified existing Jess identity avoids another account, if owner-approved. Never delete shared Auth users as rollback: legacy CV user FKs have ON DELETE CASCADE.

`generate-cv` deployed source retrieval remains unavailable. `extract-cv` was reviewed earlier but was not invoked. No end-to-end CV workflow regression test has been performed. Static additive isolation is established; full Auth/CV compatibility is not certified. Existing legacy `cv`, `cvs`, `cv_files` still have RLS disabled and effective anon SELECT/INSERT grants. These existing security findings are **not fixed or expanded by this release**. Keep Jess's original documents/profile out of those tables. Follow the separate legacy remediation proposal and obtain independent permission for any legacy change. Owner must review this shared-project risk before production account provisioning; do not silently broaden this release to fix it.

### Prepared migration and provisioning procedure — not executed

Use the project's established migration runner/canonical FMB migration history; copy only these two reviewed files into that workflow. Existing remote migration history must be checked first. Do not use `--include-all`, repair history, apply unrelated migrations, seed roles or upload candidate documents to make deployment succeed. Installed Supabase CLI supports these commands; database connection credentials are not configured here:

```powershell
# After approval: supply the approved FMB admin connection from the owner's secret store.
# Never paste it into committed files, commands shown in a report, or debug logs.
# Execute in the canonical FMB release checkout, after copying the two reviewed migrations.
supabase migration list --db-url $env:JOBS4JSR_ADMIN_DB_URL
supabase db push --db-url $env:JOBS4JSR_ADMIN_DB_URL --dry-run
# Inspect output: exactly the two Jobs4JSR migrations must be pending.
# PRODUCTION WRITE — requires separate owner approval:
supabase db push --db-url $env:JOBS4JSR_ADMIN_DB_URL
```

The release checkout/connection/history reconciliation remains an owner-controlled prerequisite, not a tested migration run. Back up current schema/policies first. Do not run an unrestricted push from this Jobs4JSR-only migration folder if existing remote versions are missing locally.

After separate provisioning approval, use Supabase's administrator interface to reuse/create Jess's approved Auth identity and create a dedicated machine identity. Do not enable global signup, alter providers or change existing credentials. Record their immutable UUIDs privately. Assign memberships through reviewed SQL, replacing placeholders with verified UUIDs:

```sql
BEGIN;
INSERT INTO public.jobs4jsr_members(user_id,owner_id,kind)
VALUES ('<JESS_AUTH_UUID>','<JESS_AUTH_UUID>','reader'),
       ('<MACHINE_AUTH_UUID>','<JESS_AUTH_UUID>','sync');
COMMIT;
```

Inspect the inserted rows as administrator; on conflict, stop and review instead of overwriting an existing entitlement. Configure local `.env` privately from `.env.example`; retain `JOBS4JSR_LETTER_UPLOAD_APPROVED=false`. Only then, after facts-publication approval:

```powershell
cd C:\DEV_LOCAL\jobs4jsr
.\.venv\Scripts\python.exe -m jobs4jsr.cli sync
```

This publishes minimal vacancy/run/health facts, not CVs, full candidate profiles or SQLite files. Cloud Save/Dismiss/Applied are authoritative and are not copied back into local status_history in this phase. A sync retry is safe; partial publication is not a transaction across HTTP. Last-success advances only after all facts/health writes finish.

### Required production verification — still outstanding

After approved migrations/provisioning, inspect `pg_class.relrowsecurity`, `pg_policies` and effective `has_table_privilege` for PUBLIC/anon/authenticated on all six new tables. Verify exposed public schema and no unexpected inherited/default grants; inspect private bucket and effective Storage policies. `SELECT schemaname,tablename,policyname,roles,cmd,qual,with_check FROM pg_policies WHERE tablename LIKE 'jobs4jsr_%' OR (schemaname='storage' AND policyname LIKE 'jobs4jsr_%');` is a read-only policy inspection.

Run the real JWT/API matrix: anonymous and unrelated FMB user cannot read any board rows; Jess reads jobs/health and can save/dismiss/apply/restore; decision flags survive logout/login and fact sync; reader cannot write job facts or membership; machine can publish only assigned-owner facts/health, cannot write decisions or elevate membership; mismatched owner/FKs are rejected. Confirm signup is absent on the board, Auth login/recovery/throttling and refresh/logout work, and membership revocation blocks access immediately. Verify rows persist with the PC offline. Backend/network outages are still dependencies.

Storage grant/path tests are also outstanding, but use synthetic nonpersonal content in an approved test context. Do not enable production letter upload or use Jess's generated letters as test fixtures. The initial board should have empty letter metadata and no hosted download links.

## Cloudflare review and procedure

Existing authenticated account: `f16286e0cc21b0fb60a275765b8ca576`. Zone `maximisedai.com`: `4679ab1d6337d8c17801ca758ba28dbe`. Credentials were verified using `wrangler whoami`; no login/credential changes were performed. Existing scopes include Worker script/route writes and zone read. Wrangler warns about newer unrelated product scopes; they are not required by this simple board, and no scope expansion was attempted.

Read-only APIs returned no zone Worker route patterns; custom-domain inventory includes apex `maximisedai.com` -> `maxai`, `billing-api.maximisedai.com` -> `billing-api`, and `workspace.maximisedai.com` -> `maximisedai-workspace`. No Jess custom-domain binding or `jobs4jsr-board` script exists. Do not confuse custom domains with route-pattern inventory. Existing apex config uses a dedicated Worker plus Static Assets; Jobs4JSR follows that convention without modifying it.

**DNS-read API failed with code 10000 (Authentication error).** Therefore exact DNS conflicts or binding readiness cannot be authoritatively confirmed with available permissions. Owner must inspect the exact Jess record before binding; no credential scope change is requested or performed. A separate exact-host custom domain can be configured without editing existing apex/billing/workspace bindings, provided DNS preflight succeeds. See [Cloudflare custom-domain guidance](https://developers.cloudflare.com/workers/configuration/routing/custom-domains/).

Prepared ignored configs: `tmp/release-readiness/wrangler-unbound.json` and `wrangler-bound.json`. Both use absolute local entry/assets paths, account pinning, `workers_dev=false`, `preview_urls=false`, FMB URL and no cron. Bound config adds **only** `{pattern: "jess.maximisedai.com", custom_domain: true}`. Both passed deploy dry-run; dry-run does not validate DNS or deployment permission. Runtime/site secrets are not configured.

```powershell
# Already verified locally; no deployment:
npx wrangler deploy --config tmp/release-readiness/wrangler-unbound.json --dry-run
npx wrangler deploy --config tmp/release-readiness/wrangler-bound.json --dry-run

# PRODUCTION WRITES — run only after their separate approvals:
# First create the unbound dedicated Worker; it fails closed until configured.
npx wrangler deploy --config tmp/release-readiness/wrangler-unbound.json
npx wrangler secret put SUPABASE_PUBLISHABLE_KEY --name jobs4jsr-board
npx wrangler secret put JESS_USER_ID --name jobs4jsr-board
# Values entered via private prompts; never supply machine/admin secrets to this Worker.
# After exact-host DNS inspection and binding approval:
npx wrangler deploy --config tmp/release-readiness/wrangler-bound.json
npx wrangler deployments list --name jobs4jsr-board
```

Record version/domain/DNS identifiers and re-read bindings after deployment. Check apex/billing/workspace still map exactly as before; test unauthenticated API denial plus Jess's private flows. Do not deploy `scripts/preview.mjs`: it is a fictional local-only unauthenticated mock. [Wrangler deployment/rollback commands](https://developers.cloudflare.com/workers/wrangler/commands/) were checked against installed 4.150.0 help.

## Approval boundary and rollback readiness

The release is **locally installed and ready for an owner-controlled integration stage, not production activated**. Exact further production approvals are:

1. Apply only the two reviewed Jobs4JSR migrations to FMB, including the empty private letter bucket/policies; no uploads. Confirm canonical migration history and backup before applying.
2. Provision/reuse exact Auth users and insert their board memberships, accepting existing profile/subscription/entitlement trigger effects. No global Auth or legacy CV permission changes.
3. Configure dedicated machine credentials locally and the Worker's publishable key/owner UUID, then publish vacancy/run/health facts with letter uploads explicitly false.
4. Create/deploy only `jobs4jsr-board`, then bind only `jess.maximisedai.com` after DNS preflight. Verify real integration before exposing the domain.

No approval for hosted letters or cloud discovery is implied. Their upload flag/scheduler remain disabled/absent.

Rollback is prepared but not exercised in production because no Worker or board database objects exist yet. Before activation retain schema snapshots, local SQLite backup, route/domain/DNS inventory and released Worker version. Stop local publishing by clearing only Jobs4JSR sync URL/configuration (leave upload flag false); do not rotate shared credentials. Preserve data/decisions during rollback.

For a later Worker revision, `npx wrangler rollback <KNOWN_GOOD_VERSION_ID> --name jobs4jsr-board` is the prepared command; a first deployment has no prior version. For first-release failure, remove/disable only the newly created Jess binding through Cloudflare after approval, restoring its saved DNS state; do not delete or edit unrelated bindings. Code rollback does not undo domain or database changes.

For approved access shutdown, administrator SQL can delete only the two exact Jobs4JSR membership rows after confirming they are the release's rows: `DELETE FROM public.jobs4jsr_members WHERE user_id IN ('<JESS_AUTH_UUID>','<MACHINE_AUTH_UUID>') AND owner_id='<JESS_AUTH_UUID>';`. This closes board entitlement without deleting shared users/CVs. Do not drop tables, delete letters, restore a stale SQLite snapshot or reverse legacy grants as a routine rollback. Destructive cleanup requires separate approval and history export.

Remaining blockers: real Supabase JWT/Storage tests, canonical migration runner and admin connection, approved identities/provisioning, Auth/CV workflow validation (including unavailable generate-cv source), shared-project security acceptance, and exact-host DNS preflight. No production changes have been performed during this preparation.


## Final production preflight evidence

This section supersedes earlier readiness counts and credential availability. Repository main and origin/main were both `ebc8674c11b8e18db0b9954859c06510b59724b9` before this documentation/test branch. The named stash and private files are retained; no production writes or account sign-ins were executed.

### Exact migrations and stage recommendation

SHA256 checksums of the current local files (including their checkout line endings):

| File | SHA256 |
|---|---|
| `20261014034534_jobs4jsr_private_board.sql` | `DE174304D0E96579604AB969DD6EB682FF39777ABCF670D026FA4622B0A00C33` |
| `20261014041250_jobs4jsr_health.sql` | `5385B79A26671A688F23D71485CA222D1091AFDD6AE942699D77E90EA7A7752D` |

Production catalogue and migration-history SELECTs again returned no Jobs4JSR objects, private bucket or the two version numbers. Migration 1 requires existing `auth.users`, `auth.uid()`, Storage tables and `storage.foldername`; it introduces no functions or Auth triggers. Migration 2 requires migration 1's membership table, and its source checks reference its own run table. Apply in order, one checkpoint at a time; neither file is safe to reapply blindly. No name collision was observed.

**NO-GO for executing the production migration stage at present.** SQL/RLS review and isolated tests pass, but a verified restorable production backup, approved canonical migration history/runner and authorised admin connection have not been established. After these operational gates and owner approval are satisfied, the additive migration stage can be reconsidered independently of provisioning, publishing, DNS and hosted letters. Missing DNS access and later real-identity tests do not imply that the SQL itself is unsafe; they block their respective later activation stages. This recommendation is not permission to migrate.

### Expanded security and compatibility evidence

Production default privileges grant broad table access to anon/authenticated for objects created by postgres/supabase_admin. The expanded PGlite test recreates permissive defaults, including an even broader PUBLIC default, then applies both unchanged migrations. It verifies all six tables have RLS, anon loses SELECT/INSERT/UPDATE/DELETE/TRUNCATE, authenticated lacks DELETE/TRUNCATE, membership is not self-grantable, reader facts updates affect zero rows and publisher cannot change decisions. Storage grants to anon were deliberately supplied in the fixture: private objects still return zero rows. No policy was weakened. Existing definer RPCs, privileged project administrators and service-role bypass remain outside the app's RLS boundary; no service-role credential is used by this release.

A metadata-only fixture at `tests/fixtures/fmb-provisioning-schema.json` records inspected column defaults/constraints and trigger function definitions, without user records or credentials. A second real PostgreSQL test instantiates these schemas and executes the inspected Auth/profile/entitlement triggers with a synthetic user. The resulting profile uses `id=Auth UUID`, has `user_id=NULL` and `is_seeded=false`; subscription is active/free, entitlement limit is 1. Existing profile-limit and updated-at/version triggers are represented. No database-trigger notification/webhook was found along the inspected Auth -> profile/subscription/entitlement paths. This does not inspect external polling, Auth mail/provider hooks or frontend onboarding. Those require owner verification before creating users. The unset profile user_id is existing FMB behaviour; Jobs4JSR uses Auth IDs directly, but FMB workflows expecting profile.user_id must be checked rather than silently repaired.

New FKs use NO ACTION against Auth users: deleting a Jobs4JSR owner or member may now be blocked until board records/memberships are reconciled. This is a real account-lifecycle coupling to approve before provisioning; do not remove FKs or delete shared Auth users to bypass it. Existing CV FKs can cascade on Auth deletion. Neither legacy CV schemas nor their disabled RLS/anonymous grants were changed. Full generate-cv source/behaviour, Auth emails/recovery settings and external onboarding are still not certified.

### Executable real-API test harness

`scripts/supabase_integration.py` is prepared, not executed against production. Its default mode prints a plan and performs no network operations. It pins the FMB URL, accepts only privately supplied publishable key plus owner/publisher/unrelated real JWTs, creates no users, attempts membership writes only as approved negative tests expecting denial, and never uses passwords/admin keys. Five local guard tests prove missing configuration or write/storage approval cannot reach fixture execution, enabled letter uploads fail closed, and a server error is not treated as access denial.

After approved migrations and identity/membership provisioning, supply `JOBS4JSR_PUBLISHABLE_KEY`, `JOBS4JSR_OWNER_JWT`, `JOBS4JSR_PUBLISHER_JWT`, `JOBS4JSR_UNRELATED_JWT` in a private process environment. Do not commit them. Read checks verify actual Auth identity and membership, anonymous and unrelated Data API denial across all six tables:

```powershell
.\.venv\Scripts\python.exe scripts/supabase_integration.py
# AFTER provisioning approval, with private JWTs supplied:
.\.venv\Scripts\python.exe scripts/supabase_integration.py --run
```

Write checks require an **empty first-release catalogue** and an explicit owner-approved environment acknowledgement. They use a unique synthetic fixture, test repeated publisher upserts, Saved/Dismissed/Applied/Restore, decision retention after fact sync, membership write denial, publisher decision denial, source health and last-sync access. No real vacancy or application decision is edited. The script prints fixture identifiers before writing so even a failed test can be reviewed/cleaned up:

```powershell
# PRODUCTION TEST WRITES — separate approval required; not run during preflight:
$env:JOBS4JSR_INTEGRATION_WRITE_APPROVAL='APPROVED_FIRST_RELEASE_SYNTHETIC_TESTS'
.\.venv\Scripts\python.exe scripts/supabase_integration.py --run --write-fixtures
```

Private Storage testing has an additional `JOBS4JSR_SYNTHETIC_STORAGE_APPROVAL=APPROVED_SYNTHETIC_STORAGE_ONLY` guard and `--storage-fixtures`. It uploads only a nonpersonal synthetic Markdown blob and tests Jess read, anonymous/unrelated download denial and cross-owner publisher upload denial. It never enables or uploads generated cover letters. If synthetic production Storage uploads are not separately approved, this test remains pending; use an approved isolated Supabase test project instead.

Session expiry/recovery checks require a genuinely expired owner JWT (`JOBS4JSR_EXPIRED_OWNER_JWT`) plus separately approved owner refresh token (`JOBS4JSR_OWNER_REFRESH_TOKEN`) and write-test approval. Auth refresh changes session state and can rotate that token; it is deliberately not part of read-only mode. Do not use a long-lived primary owner session for this test; obtain a disposable test session and sign in again afterward. Password-reset email recovery remains a separate manual, owner-approved check; no recovery email is sent by the harness.

The harness does not clean up production automatically because publisher/reader DELETE is intentionally unavailable. After tests, approved administrator cleanup must target the printed fixture job/run only, verify ownership first and preserve any concurrent real records. Source health with a pre-existing row is restored by the publisher; a newly created fixture health row requires administrator review before catalogue publication. Synthetic Storage bytes must also be removed through the Storage API/administrator interface after explicit cleanup approval, not by deleting Storage SQL metadata. Local unit tests/PGlite do not replace running this actual API matrix after approval.

### Ordered production runbook — prepared only

1. **Backup gate:** owner confirms a fresh project backup/restore point and demonstrates restoration to an isolated environment. Confirm Auth, public schema, policies/roles and migration history coverage. Storage file bytes require a separate backup/export; database backups cover metadata, not hosted files. For supplementary snapshots, approved admin connection from the secret store and Docker-supported CLI are required:

```powershell
# PREPARED READS — not executed; backups contain sensitive FMB data and stay ignored/local.
New-Item -ItemType Directory -Force tmp/release-readiness/production-backup
supabase db dump --db-url $env:JOBS4JSR_ADMIN_DB_URL --schema public --file tmp/release-readiness/production-backup/public-schema.sql
supabase db dump --db-url $env:JOBS4JSR_ADMIN_DB_URL --schema public --data-only --file tmp/release-readiness/production-backup/public-data.sql
supabase db dump --db-url $env:JOBS4JSR_ADMIN_DB_URL --role-only --file tmp/release-readiness/production-backup/roles.sql
```

These supplemental public-schema dumps are not a complete project backup. The managed Auth/Storage schemas and restore availability must be verified through the established project backup workflow. `pg_dump`/`psql` are not installed locally; CLI dump execution/restore prerequisites are not validated here. Do not proceed on the existence of an untested SQL file alone.

2. **Migration 1:** in the approved canonical FMB release checkout, reconcile remote migration history without repairing/deleting versions. Stage only migration 1 after existing historical files. Verify its checksum and `supabase db push --db-url $env:JOBS4JSR_ADMIN_DB_URL --dry-run` lists exactly migration 1. With explicit approval, run `supabase db push --db-url $env:JOBS4JSR_ADMIN_DB_URL`. Capture result/version/checksum privately. Stop on any error; do not continue automatically.
3. **Checkpoint 1:** inspect effective grants/RLS for members/jobs/decisions; confirm bucket is private and empty, and inspect all Storage policies for broader OR permissions. Verify legacy CV permissions and Auth trigger definitions have not changed. No users/memberships are provisioned yet. Existing PostgREST DDL-watch/GraphQL event triggers can reload schema automatically; this is an expected shared-project effect.
4. **Migration 2:** stage only migration 2 next; dry-run must now show exactly that file. Apply through the same approved runner. Inspect run/check/health RLS and composite FKs. Read queries can be executed in the approved SQL editor:

```sql
SELECT c.relname,c.relrowsecurity,
       has_table_privilege('anon',c.oid,'SELECT') AS anon_read,
       has_table_privilege('authenticated',c.oid,'TRUNCATE') AS auth_truncate
FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
WHERE n.nspname='public' AND c.relname LIKE 'jobs4jsr_%';
SELECT table_name,grantee,privilege_type FROM information_schema.role_table_grants
WHERE table_schema='public' AND table_name LIKE 'jobs4jsr_%';
SELECT schemaname,tablename,policyname,cmd,roles,qual,with_check FROM pg_policies
WHERE tablename LIKE 'jobs4jsr_%' OR (schemaname='storage' AND policyname LIKE 'jobs4jsr_%');
SELECT id,public,file_size_limit,allowed_mime_types FROM storage.buckets WHERE id='jobs4jsr-letters';
```

5. **Provisioning gate:** verify Auth email/provider hooks, account recovery, profile/subscription/entitlement lifecycle and unavailable CV function source, or obtain explicit owner acceptance of precisely unresolved shared-workflow risks. Use an existing approved identity where possible; create dedicated publisher only after approval. Do not directly INSERT auth.users. Approved administrator provisioning/invite may send mail and creates shared FMB rows. Use the membership SQL above only after verifying immutable IDs and roles. Never allow self-provisioning or global signup changes.
6. **Integration gate:** run the harness with real JWTs, then owner-reviewed synthetic write/Storage tests as approved. Confirm logout/login persistence, expired-session handling, cross-user denials and publisher separation. Failed tests mean stop; do not broaden RLS. Clean up only synthetic fixtures through reviewed administrator actions.
7. **Catalogue gate:** verify all fixture rows/bytes are removed; keep upload flag false, configure only the narrowly entitled publisher, then execute `python -m jobs4jsr.cli sync`. Verify 11 existing qualifying jobs (or the current verified local catalogue), no duplicate stable IDs, correct source checks and last-success timestamp, and no letters/metadata/decision overwrites. No scheduled discovery or cloud worker is created here.
8. **Disable/rollback:** stop publisher by removing its Jobs4JSR URL/configuration; preserve upload flag false. If already provisioned, revoke only the exact new memberships under administrator approval. Keep additive tables/history, and use the existing Worker rollback/binding procedure only if independently deployed. Before provisioning, an empty migration can be reversed only through a separately reviewed rollback migration, checking all new tables and bucket contain zero records first and removing dependent source checks/decisions before parent tables. Never use DROP CASCADE, manually erase migration history, delete shared Auth users, disable RLS, or restore stale private SQLite over newer decisions. With any data present, prefer disabling access and exporting/reconciling data rather than destructive rollback.

### Current Cloudflare access and preservation

Fresh direct GETs of routes, domains and exact Jess DNS now all return code 10000, Authentication error. No login/token replacement or permission change was attempted. The previous successful inventory is historical evidence only, not confirmation that bindings are unchanged today. It included `maximisedai.com`, billing/billing-api, opps and workspace services. **Jess hostname availability is unverified.** Existing prepared exact-host configs remain dry-run-only; no deployment or binding is authorised. Owner must restore/approve read access and inspect exact DNS before the later Cloudflare stage; do not infer a free hostname from failed queries.

Private .env still has generated-letter upload false, no publisher credentials or configured URL. Named stash, SQLite/CVs/letters and Windows scheduling remain preserved. This preflight changes only documentation, test fixtures and guarded test tooling. Production activation remains stopped for owner review.


Preflight validation: **46 Python tests and 12 Node/PostgreSQL tests pass**. Integration harness plan mode ran locally without network access; no production JWT/API tests were executed. Both migration checksums remained unchanged. All 27 private hashes, SQLite jobs/runs/status_history, named stash object and Windows task XML remain unchanged. No application code or production configuration changes are included in this branch. If a forbidden membership negative test ever succeeds after approval, stop immediately and have the administrator remove only the unexpected test entitlement before any real publication; do not claim a passed denial or continue testing.
