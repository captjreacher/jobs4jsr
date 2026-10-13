# Jobs4JSR

Local hospitality vacancy discovery, candidate evidence review, Word letters and offline reports. Python 3.11+ (verified here with Python 3.14), SQLite and Windows Task Scheduler. No subscription or AI API is needed. No application is submitted and no email is sent.

## Jess’s everyday use

Open `outputs/reports/latest.html` in a browser. Click the advertisement and Word letter, edit the letter and apply yourself. The job ID is the first column. Change status in PowerShell from the repository:

```powershell
.\.venv\Scripts\python.exe -m jobs4jsr.cli list
.\.venv\Scripts\python.exe -m jobs4jsr.cli status 1 Reviewed
.\.venv\Scripts\python.exe -m jobs4jsr.cli status 1 Applied
.\.venv\Scripts\python.exe -m jobs4jsr.cli report
```

Statuses: New, Reviewed, Applied, Interview, Rejected, Closed. Status changes have a separate audit history and leave advertisement details intact. `report` shows all history; `report --run initial` shows the initial five. HTML/Markdown links are relative and work offline. The browser scrolls the table on small screens.

## Install or recover

```powershell
cd C:\DEV_LOCAL\jobs4jsr
.\scripts\setup.ps1
.\.venv\Scripts\python.exe -m jobs4jsr.cli profile --source C:\DEV_LOCAL\TEMP
.\scripts\run_initial.ps1
.\scripts\install_schedule.ps1
```

The source folder and original documents are never modified. `profile` extracts PDF, DOCX and text into ignored private storage. This existing installation already contains a reviewed profile. On a fresh checkout it produces `profile_draft.json` and extracted documents, then stops for human review: fill `data/private/reviewed_profile.json` with verified facts, uncertainties and template style, and rerun `profile`. This deliberate review gate prevents extraction from becoming invented candidate experience. Do not claim capabilities from a template placeholder. The JSON experience entries need role, employer, start/end and a nonempty duties list. Skills are lower-case strings.

Private review artifacts: `data/private/document_review.md`, `candidate_summary.md`, `jess_profile.json`, `reviewed_profile.json`, extracted documents and source SHA256 hashes. Back these up locally if needed. GitHub cannot restore them. After source changes, review and edit the reviewed profile before rerunning profile. `letters` regenerates letters from the current verified profile.

## Manual searches and reports

```powershell
.\.venv\Scripts\python.exe -m jobs4jsr.cli initial
.\.venv\Scripts\python.exe -m jobs4jsr.cli scheduled
.\.venv\Scripts\python.exe -m jobs4jsr.cli report --run initial
.\.venv\Scripts\python.exe -m jobs4jsr.cli letters
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Initial discovery fills up to five recommendations and may resume a shortfall. Scheduled mode finds at most three new vacancies per due slot. Repeat execution of a completed slot is a no-op. A slot is the latest Monday/Wednesday/Friday at or before 09:00 Auckland time. A manual scheduled invocation before today's 09:00 catches up the prior due slot. A failed source produces a report and exit code 2, with retries allowed; unexpected errors return nonzero. No empty results are described as successful searches when sources failed.

## Sources and limitations

The executed automatic adapter reads Star Group’s public sitemap and specific employer advertisements, honours robots.txt and crawl delay, waits at least one second between requests, uses timeouts and logs source/per-vacancy failures. It checks live JobPosting metadata, expiry and a visible application action. This establishes that an advertisement appears open, not a guarantee an employer is still recruiting. Missing known venue coordinates are excluded with diagnostics. It searches FOH job URLs on this employer; it does not cover every target role or every Auckland employer.

SEEK NZ, Trade Me Jobs, Indeed NZ, Accor and recruiter search results were researched interactively. Their broad search pages and stale or unsupported listings are not treated as verified recommendations. Scheduled scripts cannot use Codex browsing. These boards have no configured automated provider in this release; do not bypass restrictions. Add another permitted sitemap adapter/provider only after reviewing that site's terms and robots rules. No paid search provider is required or configured. This source breadth limitation may produce fewer than three new matches, including zero on many runs. Public employer data can change shape; failures appear in reports and logs.

Configuration is copied to ignored `config/settings.json` from the public example. Edit it locally. Reference point: fixed Auckland CBD reference point near Queen Street, latitude -36.8485 longitude 174.7633. Radius is 10 km using Haversine, Earth radius 6371.0088 km; it is not driving distance. Venue coordinates are approximate and recorded with their evidence basis. North Shore venues may have much longer travel routes. Unknown locations are not guessed. Prioritise closer venues using scoring. Existing venue map is intentionally conservative.

Visible employment type overrides conflicting structured data, with both retained in the database. Salary and hours remain Unknown unless provided. Work rights, availability, barista capability and table-service experience require evidence. Mandatory qualification heuristics exclude unsupported obvious cases; a human must still review every job and letter. This implementation uses deterministic scoring and writing, not an external AI service.

## Scoring rubric

Maximum before gaps is 100: target role 20; verified transferable customer service 20; advertised customer service 15 (5 without explicit phrase); team/communication 10; training/learnability 15 (5 without evidence); location 15 within 2 km, 12 within 5 km, 8 within 10 km; posting within 30 days 5. Deduct 10 where table service is not documented. Scores express this rubric, not probability of employment. Reject out-of-radius, irrelevant/senior/management roles, unsupported barista roles and identified mandatory specialist requirements. Unknown minor preferences are flagged rather than rejected.

## Persistence and deduplication

Ignored SQLite database: `data/private/jobs.sqlite3`. Jobs store source, canonical URL, vacancy ID, original title, venue, location, coordinate basis, distance, description, first found, last verified, publication date, score, letters and run ID as JSON payload. Status is separate. Runs record timestamps and diagnostics. Status history is append-only through the CLI. Canonical URL comparison strips tracking parameters; normalised employer/title/location comparison detects cross-site copies. Distinct vacancy IDs from the same provider posted at least 30 days apart permit a conservative repost. Different-provider IDs and dates alone never establish a new vacancy. Ambiguous reposts remain duplicates. Same-URL changed advertisements stay the same record. SQLite BEGIN IMMEDIATE serialises searches and run IDs enforce idempotency. Reports/letters are generated before the transaction commits; a crash may leave orphan output files, but retry will safely regenerate them.

## Local schedule

Task: `Jobs4JSR Discovery`. Monday, Wednesday and Friday, 09:00 local time. The installer requires Windows `New Zealand Standard Time` (Pacific/Auckland) and creates a boundary without UTC offset, so Windows applies daylight-saving changes. Do not change the computer's timezone without reinstalling/reviewing the task.

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

Tests cover distance, scoring exclusions, deduplication and reposts, text/DOCX extraction, document generation, escaped reports, local links, status history, due slots and run uniqueness. Live employer discovery and Task Scheduler execution are checked separately; mocked tests are not proof of a live provider. DOCX visual verification uses LibreOffice with the document renderer when available; LibreOffice is optional for daily discovery. Scheduled future runs create reviewable letters but do not automatically render them. Review Word output before applying.

No ongoing subscription fees. Dependencies are the pinned Python packages in requirements.txt, Windows scheduling, internet access for discovery, and a Word-compatible editor for review. README, code, tests, example configuration and scripts are safe to push; candidate data and application history stay local.
