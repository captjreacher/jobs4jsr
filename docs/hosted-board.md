# Private board Phase 1

This branch prepares the first board for Funk My Brand (`qnvihygrnfgpmsznayje`) and a dedicated Cloudflare Worker. Production activation is not part of this delivery. PRs #1 and #2 were confirmed merged before this branch was created from main `680e9cb`. Prior uncommitted drafts remain in the original checkout; this implementation is in `C:\DEV_LOCAL\jobs4jsr-phase1`.

## Local operation

Use Python 3.11+, install `requirements.txt` into a venv, and run with `PYTHONPATH` set to this branch's `src`. To use the existing private configuration/history without copying personal files:

```powershell
$env:PYTHONPATH='C:\DEV_LOCAL\jobs4jsr-phase1\src'
$python='C:\DEV_LOCAL\jobs4jsr\.venv\Scripts\python.exe'
& $python -m jobs4jsr.cli --root C:\DEV_LOCAL\jobs4jsr baseline
& $python -m jobs4jsr.cli --root C:\DEV_LOCAL\jobs4jsr report
& $python -m jobs4jsr.cli --root C:\DEV_LOCAL\jobs4jsr list
& $python -m jobs4jsr.cli --root C:\DEV_LOCAL\jobs4jsr letters --job-id 12
```

The last example uses a placeholder local ID: choose one from `list`. Additional letters are generated on explicit local request. Baseline scans all enabled sources without a result cap; the baseline's best three open matches are recommendations. Subsequent runs retain all new qualifying vacancies and recommend at most three newly discovered jobs. Existing letters/history are retained. Closed is based on explicit expiry/closure/404/410, not absence from a feed. Incomplete source checks mark unobserved jobs verification-unknown; recovered verification restores open. Alternative live source evidence keeps a vacancy open despite closure of its original copy.

Baseline/manual IDs never consume scheduled slots. Partial runs retain successful sources and can be retried; a completed scheduled slot is idempotent. Report links resolve locally; jobs without a letter say to generate locally. Reports/database/letters remain gitignored. The installed Windows task remains M/W/F 09:00 Pacific/Auckland, requiring a running PC and signed-in user, with latest-slot catch-up. No cloud scheduler is created. The task points at the original checkout, not this feature worktree; owner-reviewed code must be installed there after merge without overwriting preserved drafts.

## Prepared backend

Apply neither SQL file until owner approval. Migration 1 introduces membership, vacancy projection/source aliases, independent Saved/Dismissed/Applied flags and letter metadata. The base release does not create a Storage bucket; separately approved owner-only hosted-letter setup is in `supabase/optional/jobs4jsr_letters_owner_only.sql`. Migration 2 adds discovery runs, per-run source checks and last successful sync. RLS is enabled immediately with explicit grants; anon has no access. Membership records can only be provisioned by an approved administrator. Reader identity equals owner; a narrowly entitled sync identity can publish for that owner but cannot change decisions or grant membership. No service-role key is used by Python or Worker. Existing FMB users are not admitted by signing in alone.

New board tables use the public schema with `jobs4jsr_` names. Confirm that schema is exposed via the Data API and inspect inherited/default privileges in production before activation. Existing CV tables/policies are not touched. PGlite tests exercise real PostgreSQL RLS against simplified Auth/Storage stubs; they do not substitute for real Supabase JWT/Storage API tests after approved migration.

## Synchronisation

After approved backend and machine-account provisioning, copy `.env.example` to the **private data root** `.env`. Fill only that project's publishable key, a dedicated machine Auth email/password and Jess's immutable Auth UUID. Keep `JOBS4JSR_LETTER_UPLOAD_APPROVED=false` until separate letter privacy approval. The loader accepts plain KEY=value lines, optional surrounding quotes and whole-line comments, with process environment taking precedence. Never commit it or share machine credentials in browser configuration.

```powershell
& $python -m jobs4jsr.cli --root C:\DEV_LOCAL\jobs4jsr sync
```

Sync publishes an allowlisted projection, stable persisted UUIDs, source aliases, run/source health and a final last-success timestamp. It never uploads CVs, the full profile, job descriptions, whole SQLite files or decision writes. Existing legacy application status is an initial display hint; cloud decisions take precedence. Cloud decisions remain authoritative on the board and are not written back to local status_history in this phase.

Upserts use stable keys. Failed/partial publication is recorded locally in `sync_runs` without logging credentials or upstream bodies; rerun `sync` safely. A failure halfway through publication can temporarily leave mixed updated/stale facts; the last-success timestamp only advances after the complete publication. No transaction spanning HTTP and Storage is claimed. Immutable letter content-hash paths prevent destructive overwrites. With letter approval disabled the `letters` field is omitted, so previously approved hosted metadata is preserved. When enabled, DOCX/Markdown under `outputs/letters` are eligible; review every existing generated letter before enabling the flag, since old letters as well as new recommendations can be published. The publisher rejects paths outside that directory.

After a discovery run, sync runs only when configured, including source-partial results so cloud diagnostics stay visible. Discovery history commits first; failed sync never removes local results. A completed scheduled slot will not rediscover to retry sync: use the explicit sync command. The site reads Supabase, so the latest published catalogue/decisions remain usable when the PC is offline. Backend/network outages still prevent access.

## Worker and local previews

```powershell
npm ci
npm test
npm run package
npx wrangler dev --local --ip 127.0.0.1 --port 8787
```

`wrangler.json` uses Static Assets and the FMB project URL, no routes, no cron and `workers_dev=false`. Copy `.dev.vars.example` to ignored `.dev.vars` for local owner/publishable-key configuration. No signup endpoint exists. The Worker verifies Auth identity and a live reader membership for every request, including downloads. It uses secure HttpOnly SameSite cookies, CSRF origin checks, refresh, logout, no-store private responses and CSP. Do not replace membership with user-editable metadata. Password recovery and production login-rate controls need verification in the existing FMB Auth configuration before launch; no global signup/provider settings are changed by this branch.

`npm run preview` serves a clearly marked fictional board on `127.0.0.1:8790`, without Supabase or real personal records, for UI review. It is an intentionally unauthenticated **local-only mock**, not the Worker, and must never be deployed. Actual Worker preview starts with an unconfigured 503 until required settings are supplied. Its build and runtime are verified separately from the mock. The frontend includes All Jobs, Saved, Applied and Dismissed, reversible Dismiss and filters by employer/role/location, separate top recommendations, source/discovery/verification/match details and authenticated letter links when approved files exist. There is no paid dashboard or hosted web server dependency beyond Cloudflare/Supabase.

## Release approvals and steps

The owner's instruction explicitly withholds activation. Obtain separate approvals for:

1. Merging this PR and installing reviewed code in the original checkout, preserving the old drafts and private files.
2. Applying these production migrations to FMB after reviewing effective grants and Storage policies; no legacy CV changes are bundled.
3. Creating/inviting Jess and the dedicated sync user, adding their exact memberships, and configuring machine/Worker credentials securely. Account creation may trigger existing FMB hooks/entitlements: compatibility-check first. Do not change global signup settings as a shortcut.
4. Uploading reviewed generated cover letters to this specific private bucket. Until approved, the upload flag stays false and cloud letter links are absent.
5. Deploying the dedicated Worker and binding `jess.maximisedai.com`/DNS after checking existing routes. No apex Worker routes should change.

After approval, back up schema and local SQLite; apply migrations in order through the normal reviewed release workflow. Test anon and unrelated-user denial, Jess read/decision access, publisher fact/health writes without decision access, and owner-path private Storage downloads using real JWTs. Confirm Auth recovery/session expiry and approved membership, then publish facts, validate links and deploy/bind only the dedicated domain. Keep signup disabled on the board. Do not alter M/W/F task configuration or introduce another scheduler.

## Rollback

Before first release retain current Worker artifact/config and SQLite backup. Disable sync by removing only local Jobs4JSR sync configuration; do not rotate shared project credentials. Revert Worker to its previous version or remove only the newly approved domain binding if necessary. Leave additive tables/letters/history intact during incident triage; removing data is a separate destructive approval. Revoke board memberships to close access if approved, rather than changing project-wide Auth. Restore code after preserving private files; do not blindly replace SQLite because later application decisions could be lost. Legacy CV remediation has its own compatibility plan and rollback, below.

## Costs and remaining checks

No paid discovery or AI APIs are introduced. Backend/Worker usage may fit existing quotas, but current shared utilisation/billing is unverified; review the architecture assessment's cost estimates. Dependencies: Python/requests/python-docx/pypdf/tzdata for local work, SQLite, Supabase Auth/Postgres/Storage, Cloudflare Static Assets; pinned Wrangler/PGlite are development-only. No production users, migrations, cloud uploads, DNS binding or deployment have been exercised in this phase. Local QA evidence is recorded in `docs/phase1-validation.md`.
