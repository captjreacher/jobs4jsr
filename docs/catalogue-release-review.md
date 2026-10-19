# Jobs4JSR catalogue — release approval review

Review date: 19 October 2026 (Pacific/Auckland). Production access during this
review was read-only. No migration, merge, push or deployment was performed.

## Verdict

| Area | Result | Evidence / qualification |
| --- | --- | --- |
| Additive schema | PASS | One nullable `timestamptz` column; no default, backfill, new table, trigger, function, policy or destructive SQL. Local PostgreSQL test proves existing job data and decision flags are unchanged. Old Worker remains compatible after adding the column. |
| RLS and Jess-only access | PASS | Live RLS enabled; only authenticated SELECT/INSERT/UPDATE grants; no anon/PUBLIC grants. Live policies require owner = auth.uid() and reader membership, with both USING and WITH CHECK for UPDATE. Composite job/owner FK retained. Exactly one reader and one sync member. Local tests prove sync/uninvited users cannot read/write seen state, owner cannot reassign ownership, and anon cannot access it. Worker also checks configured Jess UUID and live reader membership. |
| Seen-state logic | PASS | Authenticated same-origin POST; server timestamp; insert ignores existing rows; PATCH updates only seen_at and only if null. Repeated first-seen writes preserve the first timestamp and every decision flag. Filters and tab selection run before grouping. One group per job. |
| First-release history | WARNING — expected | No viewing history exists. All 11 current jobs start NEW; history is not invented from discovery date or Saved state. |
| Deployment compatibility | PASS | New nullable column is backward compatible. Schema must precede new Worker/UI. Existing Worker name, domain routes and secrets are retained. Dry-run build checked. |
| Production smoke verification | WARNING — pending approved release | Real new-column JWT/Data API writes and deployed UI cannot be proven before approval to migrate/deploy. Run the checks below during release; local PostgreSQL and browser tests are not a claim of deployed verification. |

No technical blocker was found. Production remains behind the explicit approval
gate. No new production permissions or shared Auth settings are required.

## Exact first-release classification

Read-only live inspection found 11 jobs, one owner, all open, all with original
`vacancy.found = 2026-10-14`. One existing decision row is Saved; none are Applied
(including legacy fallback) or Dismissed. The live table has no seen_at column.

Immediately after adding the nullable column, that decision has seen_at = NULL;
the ten jobs without decisions also have no seen state. With current data and
no filters: **NEW 11 / RECENT 0 / EARLIER OPPORTUNITIES 0**. The Saved tab has
**NEW 1**. Filters still reduce those counts normally. Recommendations stay in
their own area.

A job becomes seen only when at least half its catalogue card is visible for one
continuous second in a visible document. Collapsing NEW prevents hidden cards
being marked seen. Recommendation summaries do not mark cards seen. Classification
is stable through this visit; reload/sign-in reads persisted seen state.
Seen jobs discovered on 14 October become RECENT on fresh visits through 21
October inclusive, and EARLIER from 22 October, using Auckland calendar dates.
Unseen jobs remain NEW regardless of age. If release occurs later, the same rule
uses that actual date. New discovery activity or Jess's decisions between review
and release can change counts; rerun the read-only preflight before migration.

## Corrections and strengthened verification

No production SQL or application-logic correction was required by the review.
The browser fixtures now use valid UUID-shaped IDs instead of single letters,
and the response waiter is registered before scrolling to avoid a timing race.
Additional tests prove migration preservation, unchanged policies, repeat seen
writes, denied seen access for sync/stranger/anon, owner reassignment denial,
11-job initial classification, keyboard expansion and collapsed-card behaviour.
The older hostname document's version is historical; the rollback target below
comes from a fresh Cloudflare deployments-status read.

## Release sequence — execute only after explicit approval

1. Freeze and review the release candidate. Changes currently exist uncommitted
   on local main at `c3c814ea1ec95002eeb467bfc98441c794ac8c5f`, matching remote
   main at review time. Put only the catalogue changes/tests/review notes on a
   `codex/catalogue-grouping` branch and reviewed PR. Pin its commit SHA. Do not
   merge or deploy an unreviewed working tree. No automatic deployment workflow
   exists in this checkout. If main moves, reconcile and rerun the full checks.
2. Capture the current Worker version with
   `npx wrangler deployments status --name jobs4jsr-board`. The version observed
   at review is **068927c5-f599-4ff4-a8ea-944713eb370a (100%)**. Reconfirm at
   release time, retain that ID/config, and record a private before-snapshot of
   Jobs4JSR job IDs, decision rows and policy/grant definitions. Do not export
   credentials into this repository. Confirm the target is Supabase project
   `qnvihygrnfgpmsznayje` and seen_at is still absent. If it already exists,
   inspect its type/history and stop rather than blindly applying/retrying SQL.
3. Apply exactly the reviewed optional SQL file using Supabase `apply_migration`
   with `project_id = qnvihygrnfgpmsznayje`,
   `name = jobs4jsr_seen_at`, and this query:

   ```sql
   alter table public.jobs4jsr_decisions add column seen_at timestamptz;
   ```

   This is a one-time tracked migration, not an execution of all repository SQL.
   Do not run `supabase db push`: this shared project's remote history contains
   migrations from other applications not represented in this repository.
   Do not apply either base migration again. The optional file is the reviewed
   SQL source; retain the generated remote version/name in the release record.
   A brief ALTER TABLE lock is required; use a short lock timeout in the
   migration session if operational contention is observed, and abort/retry
   safely rather than allowing a blocked release to queue indefinitely.
4. Before deploying, verify information_schema reports nullable timestamptz with
   no default; compare existing jobs/decisions/flags to the before-snapshot;
   confirm existing decision seen_at values are null and policies/grants/RLS/FK
   are unchanged. Confirm the migration appears once in migration history and
   that the Data API schema cache exposes seen_at with Jess's authenticated
   read. The old Worker must still serve jobs/decisions. On any mismatch, stop
   before deployment; leave the additive column in place for investigation.
5. Merge the reviewed PR only after migration verification. Checkout the merged
   main in a clean release checkout. Record its SHA and run, in order:

   ```powershell
   npm ci
   npm test
   .\.venv\Scripts\python.exe -m unittest discover -s tests -v
   npm run preview
   ```

   Keep the local-only preview running in a separate terminal; run
   `npm run test:ui` with Playwright installed or PLAYWRIGHT_MODULE set to its
   module URL. Then run `npm run package` (dry-run) and `git diff --check`.
   Only continue if all exit successfully. Use the checkout's existing Python
   environment or recreate it from the pinned project requirements first.
6. Deploy Worker and static assets together from that exact merged commit:

   ```powershell
   npx wrangler deploy --config wrangler.json --name jobs4jsr-board --keep-vars
   ```

   Keep both Custom Domain routes (`jess.funkmybrand.com` and the legacy redirect
   host), `workers_dev=false`, SUPABASE_URL and existing secrets JESS_USER_ID /
   SUPABASE_PUBLISHABLE_KEY. Do not recreate the Worker, rewrite secrets, change
   DNS/Auth settings, republish discovery data or alter the discovery schedule.
7. Record the new version with `npx wrangler deployments status`. At
   `https://jess.funkmybrand.com`, verify signed-out API access is denied; sign
   in as Jess; confirm initial counts relative to the snapshot, Saved state,
   recommendations, filters, accordion defaults and readable update copy.
   Observe one job and verify exactly its seen_at becomes non-null while all
   flags remain unchanged; reload and confirm its correct age group. Check
   desktop/mobile layout. Verify Save/Unsave/Dismiss/Restore using a designated
   job and restore its original reversible flags. Verify applied behaviour via
   automated tests; do not mark a real job Applied just for a smoke test because
   the existing UI has no undo. Do not submit applications or send messages.
   Confirm an uninvited account and sync identity cannot access seen decisions
   using existing approved test identities; do not create new accounts for this.
8. If live checks fail, rollback the Worker with
   `npx wrangler rollback <captured-version-id> --name jobs4jsr-board` and verify
   the old UI. Retain the nullable column and all decisions/seen timestamps.
   Do not drop columns, restore an old database snapshot over new decisions, or
   revert shared Supabase settings. Record failure and follow up separately.

The post-migration/PostgREST and post-deployment smoke checks are release steps,
not checks falsely claimed complete during this read-only review.

## Fresh local validation

Results recorded after the review changes:

- `npm test`: 25/25 passed, including real PostgreSQL migration/RLS tests.
- Python unittest suite: 46/46 passed.
- Browser checks: desktop 1280×900 and mobile 390×900; defaults, 44px+ touch
  targets, no overflow, keyboard, collapsed unseen cards, toggle persistence,
  seen writes, Saved/Applied/Dismissed/Restore and fresh-visit classification.
- `npm run package`: passed (dry-run only). `git diff --check`: passed.

Screenshots remain in ignored `tmp/catalogue-evidence/1280.png` and `390.png`.
