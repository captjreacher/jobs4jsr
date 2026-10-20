# Manual Run Update — local implementation and staged release

Status: review candidate; no production migration, task installation, merge,
deployment or live discovery is authorised by this document. The Worker and
poller both default to disabled for manual updates. Existing production data
and the installed task are not changed by the tests.

## Architecture and execution guarantees

The board POSTs only an idempotency UUID to its existing Worker. The Worker
verifies the configured Jess UUID, live reader membership and same origin, then
uses the reader JWT for the request RPC. Supabase stores the request durably.
No browser-to-PC connection, command, source URL or candidate data is accepted.

The outbound poller uses the existing sync identity and the same canonical
`--root` as the discovery task. It polls every 30 seconds; during an execution
it heartbeats every 20 seconds. Claims last two minutes. Requests expire after
24 hours unclaimed, and have at most three attempts, with 60/120-second retry
delays after explicit failures. A one-minute database cooldown and a unique
active-request index coalesce repeated clicks, tabs and lost-response retries.

The poller acquires a Windows file lock before claiming. The same reentrant lock
wraps scheduled/manual discovery, standalone sync and letter writes, and stays
held through publication. A deferred scheduled slot is written to a separate
SQLite control database before acquiring the lock; it is not blocked by the
main catalogue transaction. The poller runs deferred scheduled slots before
manual requests, with the original scheduled ID. Crashed running slots remain
recoverable. After three failed attempts a slot remains recorded as failed for
operator recovery; it is not deleted or silently treated as completed.

The installed `Jobs4JSR Discovery` task is Monday–Friday 02:00 Pacific/Auckland,
with its current action, IgnoreNew policy and 20-minute task limit. Those scripts,
triggers and scheduler slot calculation are unchanged. Only the common CLI
execution envelope is coordinated. Manual requests never consume scheduled IDs.

The existing adapters/scoring/deduplication/reconciliation run unchanged as a
sourcing engine. A small reconciliation result addition counts distinct existing
jobs positively refreshed rather than counting cross-source duplicate matches.
A summary checkpoint is committed in the same main SQLite transaction as the
discovery changes. Failed publication resumes from that checkpoint without
rediscovery. Partial-source results publish with warnings; all-source failure
is reported failed, while retained results remain available.

Manual publication uses a single RPC transaction that locks/checks the current
request token and unexpired lease, writes jobs/run/check/health projections and
finalises the request. Stale tokens cannot publish. Repeating a completed claim
after a lost response returns its terminal receipt without writing again. A
later poll reconciles local unpublished checkpoints against terminal receipts.
Decisions, seen state and existing letter metadata are not in this payload.
Manual execution refuses cloud letter-upload mode; the current board has that
separately approved enhancement disabled. Existing scheduled publication remains
compatible with its previous letter-upload configuration.

Discovery runs in the poller process, not an orphanable subprocess. A separate
watchdog, independent of heartbeat HTTP calls, terminates that process on a
20-minute execution deadline or 90 seconds without a confirmed heartbeat. OS
locks are released and uncommitted SQLite changes roll back. The Windows task
restarts the poller; expired leases and durable checkpoints provide recovery.
Processing is retryable with idempotent effects, not exactly-once networking.

## Database and security review

`20261020043915_jobs4jsr_manual_updates.sql` adds two RLS tables and restricted
RPCs; it does not alter existing policies, jobs, decisions or seen history.
There are no new credentials, service-role keys or auth accounts.

- Readers may enqueue and inspect only their owner scope. They cannot claim,
  heartbeat, complete requests, change queue rows or SELECT claim tokens.
- Sync membership is rechecked by privileged helpers; runner identity is bound
  in runner status. Reader and sync permissions are distinct.
- Privileged bodies are in a non-exposed schema with empty search_path and fully
  qualified relations. Exposed wrappers are SECURITY INVOKER. PUBLIC/anon
  execution is revoked. Direct table writes are not granted to authenticated.
- RPC transitions use server time, per-owner transactional advisory locks,
  row locks, conditional token/lease checks and the active-request unique index.
- Publication checks existing ownership on every job/run/check upsert and rolls
  the whole transaction back on mismatch/error. Existing decisions/seen rows
  are never updated by publication.
- Browser responses are allowlisted and exclude claim tokens, credentials,
  runner identity and internal lease/attempt controls. Errors are generic;
  source warnings contain configured source names, not exception bodies.
- The existing sync account already has direct publication rights for the
  scheduled pipeline. This release does not narrow those existing rights.
  Fencing protects this implementation's manual RPC path, not a malicious holder
  of that trusted account. One canonical local database/runner installation is
  required; multiple independent PCs/databases are not supported.

## Local verification

Run with the project's virtual environment (no live credentials are required):

```powershell
npm ci
npm test
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
npm run preview
```

In a second terminal with Playwright installed or PLAYWRIGHT_MODULE pointing to
its module URL, run `npm run test:ui`, `npm run test:updates:ui`, then
`npm run package` and `git diff --check`. Preview uses fictional fixtures only.
Evidence is written under ignored `tmp/manual-update-evidence/`.

Coverage includes real local PostgreSQL grants/RLS, duplicate requests, claims,
expired/stale tokens, retry delays/exhaustion, atomic rollback, acknowledgement
replay, offline status and rollback/reapply of the additive schema. Python tests
exercise two separate processes competing for the real OS file lock, scheduled
deferral/crash recovery, publication checkpoint replay, counts and watchdog
behaviour. Browser tests cover desktop/mobile status transitions, touch targets,
source warnings and completion refresh with preserved filters/accordions.

## Staged production release — separate authorisation required

1. Review the PR/security boundaries and all check output; approve migration,
   canonical local code update, poller installation and Worker deployment
   explicitly. Capture the current production Worker version, scheduled-task XML,
   database decisions/seen state and private local SQLite/control files. Do not
   capture credentials in committed evidence. Use the existing Supabase connector
   for read-only migration history; linking/reconfiguring the project is not a
   prerequisite. Never run a broad db push against the shared project history.
2. Apply only the reviewed additive migration to `qnvihygrnfgpmsznayje` via the
   tracked migration mechanism. Verify policies, grants, token-column denial,
   reader/sync/anonymous separation, coalescing and empty initial queue. Do not
   enable the board flag yet or enqueue live work during schema verification.
3. Merge only after approval/checks. At a safe time outside the 02:00 run, verify
   no old CLI/sync process is running against the canonical root before updating
   its code/environment. An older running process cannot acquire a lock added
   by newer code. Preserve all private files. Do not change the Discovery task's
   triggers, action/root or retry settings. Re-run tests from clean merged code.
4. Add `JOBS4JSR_MANUAL_UPDATES_ENABLED=true` to the existing private `.env` only
   after approval. Keep the existing sync credentials and owner ID. Install the
   new task with `scripts/install_update_poller.ps1 -Install`; without that switch
   the script prints review guidance and makes no changes. Its action directly
   manages the Python runner process, without a shell parent. Do not use a review
   worktree as a second data root. The task uses the current limited interactive
   Windows user, starts at logon, ignores duplicate task instances, and restarts
   on failure after one minute (up to 999 times). It requires the PC on and the
   user signed in. Start the task only when approved; even `poller --once` can
   execute real queued work and is not a harmless health check.
5. Verify the runner heartbeat with an empty queue and no live discovery; confirm
   the original task XML is unchanged. Deploy Worker/assets to the existing
   `jobs4jsr-board` with `--keep-vars`, initially without MANUAL_UPDATES_ENABLED.
   Preserve all secrets, routes and other vars. Then explicitly set the Worker
   `MANUAL_UPDATES_ENABLED=true` in reviewed release configuration and deploy.
   Do not add PC credentials to Worker/browser configuration.
6. Under explicit live-discovery acceptance approval, request one update as Jess.
   Verify durable/offline state while the poller is stopped, one claim after
   restart, correct running/completion or failure summary, atomic publication,
   counts, source warnings and refreshed board. Test a network interruption/retry
   and scheduled/manual contention without creating historical scheduled slots
   or changing the real schedule. Never force source failures against real
   employers; inject them in isolated tests. Use desktop/mobile and verify all
   existing decisions/seen state are preserved. Confirm anonymous/nonmember
   rejection and sync-only runner controls. Record active Worker/commit/migration
   IDs and the final queue state.

## Supervision and recovery

Logs: private rotating `outputs/logs/update-poller.log` (5 MB, three backups).
The optional `run_update_poller.ps1` wrapper is for supervised foreground use;
the installed task launches Python directly. Queue state lives in Supabase;
checkpoints live in `data/private/jobs.sqlite3`; deferred slots live in
`data/private/runner-control.sqlite3`. Never delete these files to clear a lock.
Inspect the exact failed slot/request and logs before retrying. Manual retries
use a new request after the terminal failure/cooldown; same-key retries return
the original request. For an exhausted scheduled slot, stop/quiesce the poller,
acquire the canonical execution lock, back up the control DB, and reset only that
known slot's state/attempts/available fields for an explicitly approved retry.
Never clear all scheduled history or substitute a manual run ID for a due slot.

## Rollback

Disable Worker MANUAL_UPDATES_ENABLED first; stop/disable only `Jobs4JSR Update
Poller`, and verify its process has exited before rolling local code back. Wait
for in-flight publication transactions to finish/leases to expire and retain
queue/checkpoint/decision data. Restore the captured Worker version if needed.
Review every deferred scheduled slot before restoring older CLI code: drain it
through the new coordinator under approval, or record its exact ID for explicit
operator recovery. Older code does not know how to drain the new control DB.
The existing Discovery task stays in place. To uninstall the poller, use
`Unregister-ScheduledTask -TaskName 'Jobs4JSR Update Poller' -Confirm:$false` only
after the separate rollback authorisation; do not uninstall Discovery.

Prefer leaving the additive database objects and audit history intact. If full
schema removal is separately authorised, first export the queue/status and apply
only `supabase/optional/jobs4jsr_manual_updates_rollback.sql`. It removes the new
RPCs, helpers and tables without CASCADE or changes to old tables. The SQL is
tested for down/up locally. Published discovery results are deliberately not
rolled back over genuine subsequent user decisions.

## Current release gate

Local implementation is for PR review. Production schema/RPC acceptance, actual
task installation/restart behaviour and live employer discovery remain untested
and unauthorised. Unit/browser/PGlite tests do not substitute for those staged
checks. No merge, production migration, installation or deployment is performed
as part of this delivery.

Final local verification on 20 October 2026: 56 Python tests and 34 Node tests
passed; both browser suites passed at 1280px and 390px; Worker dry-run packaging,
PowerShell syntax parsing and whitespace checks passed. Read-only production
preflight confirmed the manual migration is absent, neither new table exists,
no poller task is installed, and the active Worker remains
`27d57140-937d-438f-8239-acfe97b1fc25`. The installed Discovery task was verified
from PowerShell as Monday–Friday 02:00. This is review readiness, not a claim of
completed production acceptance or permission to begin the release.
