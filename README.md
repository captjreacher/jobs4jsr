# Jobs4JSR

Production private board: **[jess.funkmybrand.com](https://jess.funkmybrand.com)**. The previous hostname redirects permanently. Use Jess's existing account; see [hostname migration and deployment instructions](docs/hostname-migration.md).

Local hospitality vacancy discovery, candidate evidence review, Word letters and offline reports. Python 3.11+ (verified here with Python 3.14), SQLite and Windows Task Scheduler. No subscription or AI API is needed. No application is submitted. The weekday evening digest is the only outbound message this system ever sends.

## Jess’s everyday use

Open `outputs/reports/latest.html` in a browser. Click the advertisement and Word letter, edit the letter and apply yourself. The job ID is the first column. Change status in PowerShell from the repository:

```powershell
.\.venv\Scripts\python.exe -m jobs4jsr.cli list
.\.venv\Scripts\python.exe -m jobs4jsr.cli status 1 Reviewed
.\.venv\Scripts\python.exe -m jobs4jsr.cli status 1 Applied
.\.venv\Scripts\python.exe -m jobs4jsr.cli report
```

Statuses: New, Reviewed, Applied, Interview, Rejected, Closed. Status changes have a separate audit history and leave advertisement details intact. `report` shows all history; `report --run initial` shows the original initial discovery. HTML/Markdown links are relative and work offline. The browser scrolls the table on small screens.

## Install or recover

```powershell
cd C:\DEV_LOCAL\jobs4jsr
.\scripts\setup.ps1
.\.venv\Scripts\python.exe -m jobs4jsr.cli profile --source C:\DEV_LOCAL\TEMP
.\scripts\run_initial.ps1
.\scripts\install_schedule.ps1
```

The source folder and original documents are never modified. `profile` extracts PDF, DOCX and text into ignored private storage. This existing installation already contains a reviewed profile. On a fresh checkout it produces `profile_draft.json` and extracted documents, then stops for human review: fill `data/private/reviewed_profile.json` with verified facts, uncertainties and template style, and rerun `profile`. This deliberate review gate prevents extraction from becoming invented candidate experience. Do not claim capabilities from a template placeholder. The JSON experience entries need role, employer, start/end and a nonempty duties list. Skills are lower-case strings.

Private review artifacts: `data/private/document_review.md`, `candidate_summary.md`, `jess_profile.json`, `reviewed_profile.json`, extracted documents and source SHA256 hashes. Back these up locally if needed. GitHub cannot restore them. After source changes, review and edit the reviewed profile before rerunning profile. `letters --job-id ID` generates one letter from the current verified profile.

## Manual searches and reports

```powershell
.\.venv\Scripts\python.exe -m jobs4jsr.cli initial
.\.venv\Scripts\python.exe -m jobs4jsr.cli scheduled
.\.venv\Scripts\python.exe -m jobs4jsr.cli search
.\.venv\Scripts\python.exe -m jobs4jsr.cli search --run-id employer-check
.\.venv\Scripts\python.exe -m jobs4jsr.cli sources
.\.venv\Scripts\python.exe -m jobs4jsr.cli report --run initial
.\.venv\Scripts\python.exe -m jobs4jsr.cli letters --job-id 1
.\.venv\Scripts\python.exe -m jobs4jsr.cli baseline
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Baseline and discovery runs retain all qualifying vacancies without a result cap. The best three baseline matches, or at most three newly discovered matches on subsequent runs, are recommendations. `search` uses a separate manual run ID and never consumes a scheduled slot; it retains all qualifying matches and highlights at most three. Use an explicit `--run-id` to make manual reruns idempotent. `sources` prints persisted source checks as JSON. Repeat execution of a completed slot is a no-op. A slot is the latest weekday at or before 02:00 Auckland time. A manual scheduled invocation before today's 02:00 catches up the prior due slot. A failed source produces a report and exit code 2, with retries allowed; unexpected errors return nonzero. No empty results are described as successful searches when sources failed.

## Sources and limitations

Four independent employers are configured: Star Group; Accor Auckland hotels; Hind Management / Sudima; and Atomic Coffee Roasters. [Source research and coverage](docs/discovery-sources.md) describes their public endpoints, venue evidence and restrictions. Star Group and Accor use public sitemaps and complete JobPosting pages; Hind uses its public Workable widget feed plus specific JobPosting pages; Atomic uses its server-rendered LiveHire employer listing and JobPosting pages. No credentials or paid provider are required. Newly added source definitions were appended to this installation's private settings without replacing existing settings. Existing installations must add the new source entries from the example to their local settings; configuration is never silently overwritten on upgrade.

All adapters honour robots.txt, crawl delay, request-rate directives and redirects, wait at least one second per request and use 25-second timeouts. Every redirect destination is checked before fetching. HTTP 429 stops that employer immediately and records Retry-After; other employers continue. A source failure or broken detail page is isolated; other employers continue and still produce reports and letters. The overall command returns exit code 2 for partial or failed source checks; successful results remain saved. Only GET requests are used. Restricted job boards, blocked JobAdder widgets, blocked SmartRecruiters API endpoints, expressions of interest and incomplete listings are excluded. Advert pages are requested only where robots.txt permits it, so Trade Me and SEEK are read at listing level only, as clearly-labelled unverified leads. Scheduled scripts do not depend on Codex browsing.

Each source check stores checked time, last fully successful check, state, inspected summaries/cards, verified in-radius descriptions, qualified matches, duplicates, selected jobs, exclusions, notes and errors. Counts are per check/attempt. Qualified counts include duplicates before removal; selected counts are all newly retained additions; recommendation count is separately capped at three. A successful check means the feed and attempted descriptions were retrieved without errors, not that any suitable job exists. Later failures retain the earlier successful timestamp. A separate additive `source_checks` table preserves existing jobs, statuses and runs. Run-specific reports contain a source diagnostics table; `report --run <id>` regenerates it from the database.

Target roles include waitress/waiter, restaurant server, FOH/front-of-house, food-and-beverage attendant, hospitality team member, café assistant and hospitality guest service. The system reads qualification requirements before recommending. Unsupported barista roles and identified mandatory specialist/service experience are excluded; an entry-level café role explicitly offering barista learning can qualify. This is conservative heuristic assessment, so Jess still reviews every advert and letter.

A live employer listing, complete JobPosting and application action establish that an advert appears open; a sitemap alone does not. Expired, closed, future-dated, unknown-location and ambiguous multi-location adverts are excluded. Accor sometimes sets expiry 100 years ahead; this is flagged as a placeholder, not treated as evidence of ongoing recruitment. There is no guarantee an employer is still recruiting. Broad Auckland city labels do not automatically receive CBD coordinates: configured venue tokens must identify the workplace from the address/description. Airport hotels are never assigned CBD coordinates. Source/venue coverage is finite; new locations require evidence and configuration. Fewer than three results, including zero, remain normal outcomes.

Configuration is copied to ignored `config/settings.json` from the public example. Edit it locally. Reference point: fixed Auckland CBD reference point near Queen Street, latitude -36.8485 longitude 174.7633. Radius is 10 km using Haversine, Earth radius 6371.0088 km; it is not driving distance. Venue coordinates are approximate and recorded with their evidence basis. North Shore venues may have much longer travel routes. Unknown locations are not guessed. Prioritise closer venues using scoring. Existing venue map is intentionally conservative.

Visible employment type overrides conflicting structured data, with both retained in the database. Salary and hours remain Unknown unless provided. Work rights, availability, barista capability and table-service experience require evidence. Mandatory qualification heuristics exclude unsupported obvious cases; a human must still review every job and letter. This implementation uses deterministic scoring and writing, not an external AI service.

## Other job boards (unverified leads)

Trade Me and SEEK NZ are checked on every discovery run, but only where their robots.txt allows it and only at listing level. A lead is not a vacancy: it has no verified workplace coordinate and no confirmed application action, so it never receives a distance, a score or a generated letter, and it is never merged into the verified catalogue. Leads are shown in their own report section and in the digest email, always marked unverified.

Trade Me publishes complete JobPosting data on individual advert pages, and robots.txt permits those pages, but they carry no street address or coordinates. A Trade Me advert therefore could never satisfy this project's verified-location rule, so only its Auckland City category pages are read for leads and its advert pages are left alone.

SEEK disallows advert pages outright (`Disallow: */job/`), so only its permitted Auckland search pages are read; individual adverts are linked for manual checking and never requested.

Indeed NZ is not configured at all. Its search pages return HTTP 403 to a plain robots-obeying client and its advert pages are disallowed, so no adapter exists. A saved-search link is included in the digest for manual checking instead.

Leads are stored once per board and advert ID. A SEEK card without an advert ID is skipped rather than stored: it has no stable link and could only reappear as a new duplicate on every run. Only leads seen on the boards within the last 21 days (`digest.lead_retention_days`) are listed as current; older rows stay in `board_leads` for audit and are no longer shown in reports or digests.

Lead sources are best-effort and fail softly. A changed page format or an unavailable board is reported as `LEAD SOURCE UNAVAILABLE` in the report notes and does not alter the verified source checks or the exit code. Leads are filtered to the same target roles and the same senior, management and kitchen exclusions as a verified vacancy, and the board's own Auckland location filter is used in place of an invented coordinate, so the displayed suburb is the only location evidence.

## Scoring rubric

Maximum before gaps is 100: target role 20; verified transferable customer service 20; advertised customer service 15 (5 without explicit phrase); team/communication 10; training/learnability 15 (5 without evidence); location 15 within 2 km, 12 within 5 km, 8 within 10 km; posting within 30 days 5. Deduct 10 where table service is not documented. Scores express this rubric, not probability of employment. Reject out-of-radius, irrelevant/senior/management roles, unsupported barista roles and identified mandatory specialist requirements. Unknown minor preferences are flagged rather than rejected.

## Persistence and deduplication

Ignored SQLite database: `data/private/jobs.sqlite3`. Jobs store source, canonical URL, vacancy ID, original title, venue, location, coordinate basis, distance, description, first found, last verified, publication date, score, letters and run ID as JSON payload. Status is separate. Runs record timestamps and diagnostics. Status history is append-only through the CLI. Canonical advert and application URLs strip tracking parameters; normalised employer/title/location fingerprints handle FOH naming, ampersands, accents, group suffixes and Auckland Central/CBD aliases. Deduplication compares history and same-run candidates before writing. Cross-source copies retain the original source record and application status, with alternate verification evidence added. Distinct vacancy IDs from the same provider posted at least 30 days apart permit a conservative repost. Different-provider IDs and dates alone never establish a new vacancy. Ambiguous reposts remain duplicates. Same-URL changed advertisements stay the same record. SQLite BEGIN IMMEDIATE serialises searches and run IDs enforce idempotency. Reports/letters are generated before the transaction commits; a crash may leave orphan output files, but retry will safely regenerate them.

## Weekday evening digest email

A second scheduled task emails the new roles. It discovers nothing itself: it reads the database the 02:00 run wrote and sends only roles first found today.

- Monday to Friday at 18:00 Pacific/Auckland. Nothing is sent at the weekend.
- Sent only when a day produced new roles, so a quiet weekday sends no email; the quiet day is recorded as `skipped` in `digest_sends`.
- At most one email per calendar day. Before sending, the digest takes a durable claim in SQLite (`digest_sends`), so a retry or a second concurrent run cannot duplicate the message. The claim is held for 15 minutes and then expires, so a crashed run cannot block the evening task for ever.
- A missed weekday is caught up on: the digest covers today plus up to two earlier weekdays that were never delivered (`digest.catch_up_days`). Every role is labelled with the day it was recorded, so a carried-over role is never presented as newly found. Days further back are not resurrected.
- Verified vacancies and unverified leads are separate, clearly-labelled sections.
- Delivery uses your own SMTP account. Only `starttls` (default port 587) and `ssl` (default port 465) are accepted. Any other or missing `JOBS4JSR_SMTP_SECURITY` value is refused instead of downgraded, so the password is never sent over an unencrypted connection, and the TLS context verifies the server certificate and hostname (`smtplib`'s own default context does not). Credentials are read only from the ignored private `.env` file (`JOBS4JSR_SMTP_*` and `JOBS4JSR_DIGEST_TO`; see `.env.example`). Use an app password. The password is never logged, printed or written into a report.
- Delivery guarantee: at-most-once while a claim lease is live, at-least-once overall. SMTP cannot acknowledge a message exactly once, so a crash after the server accepted the message but before the delivery record was written can produce one duplicate on the next retry. That window is small and is visible in the log as `Digest claim attempt N`.

```powershell
.\scripts\install_digest.ps1
Get-ScheduledTask -TaskName 'Jobs4JSR Digest'
Start-ScheduledTask -TaskName 'Jobs4JSR Digest'      # send one now
.\.venv\Scripts\python.exe -m jobs4jsr.cli email    # or run it by hand
Get-Content .\outputs\logs\digest-*.log
Unregister-ScheduledTask -TaskName 'Jobs4JSR Digest' -Confirm:$false
```

New roles with no SMTP configuration fail loudly instead of silently sending nothing. A failed send is recorded as `failed` with its error in `digest_sends`, printed as `DIGEST EMAIL FAILED …` on stderr, and returns a non-zero exit code, so Task Scheduler marks the run failed and retries it. `python -m jobs4jsr.cli digest-status` lists recent digest outcomes for operational checks.

## Local schedule

Task: `Jobs4JSR Discovery`. Monday to Friday, 02:00 local time. The installer requires Windows `New Zealand Standard Time` (Pacific/Auckland) and creates a boundary without UTC offset, so Windows applies daylight-saving changes. Do not change the computer's timezone without reinstalling/reviewing the task.

Action: Windows PowerShell, NoProfile, NonInteractive, calling `scripts/run_scheduled.ps1` with the repository working directory and fixed virtualenv interpreter. Runs as the current user at limited privilege with InteractiveToken: **the computer must be on, the user signed in, and the runtime/network available**. No cloud execution is configured. StartWhenAvailable catches missed launches; the CLI collapses several missed slots to one latest slot. IgnoreNew prevents overlap. Timeout 20 minutes; two retries five minutes apart; battery operation allowed. It does not wake a sleeping PC.

Verify or remove:

```powershell
Get-ScheduledTask -TaskName 'Jobs4JSR Discovery'
Get-ScheduledTaskInfo -TaskName 'Jobs4JSR Discovery'
Start-ScheduledTask -TaskName 'Jobs4JSR Discovery'
Get-Content .\outputs\logs\*.log
Unregister-ScheduledTask -TaskName 'Jobs4JSR Discovery' -Confirm:$false
```

Logs include each invocation, including idempotent skips. Dated reports include run-specific snapshots, `report.html`/`report.md` aliases and `latest.html`. Regenerating reports changes the latest view but retains other run snapshots.

## Privacy and validation

All `data/`, `outputs/`, local configuration, `.env`, virtualenv and generated packaging metadata are ignored. Original candidate documents remain outside the repository. Never add ignored files with `git add -f`. Public code has no candidate identity, contact details or employment history. Tests use fictional fixtures.

Tests cover each employer adapter, malformed feeds and pages, robots denial, checked redirects and delays, source failure isolation, cross-source and same-batch deduplication, three-job retry budgets, manual/scheduled isolation, additive database upgrades and last-success timestamps, plus the original distance, scoring, extraction, letters, reports, history and schedule checks. Robots tests cover wildcard and end-anchor matching, longest-match and Allow ties, agent groups, a hostile many-asterisk rule, separated wildcards in bounded time and refusal of a rule too large to evaluate safely; lead tests cover both board parsers, role filtering, robots skipping, cards without an advert ID, duplicate suppression, new-only storage and stale-lead filtering; digest tests cover content, quiet-day suppression, one-email-per-day idempotency, the encrypted-only SMTP modes, rejection of unencrypted or misspelled modes, certificate verification, concurrent claims, expired-claim recovery, failed-send recording and bounded catch-up.

`npm test` runs the Node test files with `--test-concurrency=1`. Each Postgres test file starts its own WebAssembly Postgres instance, and running them all in parallel exhausts the V8 heap (`Fatal process out of memory: Zone`). Serial execution is a test-runner resource setting, not a weakened check; every test still runs. Live employer discovery and Task Scheduler execution are checked separately; mocked tests are not proof of a live provider. DOCX visual verification uses LibreOffice with the document renderer when available; LibreOffice is optional for daily discovery. Scheduled future runs create reviewable letters but do not automatically render them. Review Word output before applying.

No ongoing subscription fees. Dependencies are the pinned Python packages in requirements.txt, Windows scheduling, internet access for discovery, and a Word-compatible editor for review. README, code, tests, example configuration and scripts are safe to push; candidate data and application history stay local.
# Phase 1 private board

The private Cloudflare/Supabase board and uncapped catalogue are prepared on this feature branch. Read [operation, release approvals and rollback](docs/hosted-board.md), [validation evidence](docs/phase1-validation.md), and the separate [legacy CV security proposal](docs/legacy-cv-security-remediation.md). No production deployment is included. Baseline retains all qualifying jobs; scheduled runs retain all new matches and highlight at most three recommendations. Use `letters --job-id ID` for additional local letters.
