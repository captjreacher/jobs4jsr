# Phase 1 validation evidence

Validated locally on 14 October 2026, Pacific/Auckland. Feature worktree: `C:\DEV_LOCAL\jobs4jsr-phase1`, based on merged main `680e9cb`. PR #1 and #2 both reported MERGED before implementation.

## Automated validation

- Python: `python -m unittest discover -s tests -q` with this branch's `src` on PYTHONPATH. 41 tests pass: original adapter/transport/extraction/geography/scoring/report/schedule tests plus baseline completeness, three-letter budget, stable IDs, status preservation, uncertainty/recovery/closure, additional local letters, publisher retries/idempotency and privacy approval gate.
- Node: `npm test`. Eleven tests pass: real PostgreSQL RLS using PGlite, mocked Worker Auth/membership/cookies/CSRF/decisions/download boundaries and frontend filter/view logic. PostgreSQL tests apply both migration files to synthetic Auth/Storage schemas, and exercise anonymous denial, unrelated-user denial, Jess read/decision permissions, publisher writes without decision changes, own-path versus other-owner Storage restrictions and private bucket flag.
- `npm run package` uses pinned Wrangler 4.150.0 in deploy **dry-run** mode and produces the Worker bundle plus three static assets. No Worker is uploaded. Compatibility date is 2026-10-13, the newest date supported by the installed workerd; an initial 2026-10-14 local start was rejected and corrected.
- Actual Wrangler local preview: shell HTTP 200, unconfigured private API HTTP 503. This confirms startup and fail-closed configuration; no real Supabase Auth/API requests were made.

Mocked upstreams and PGlite are not live Supabase integration tests. No production migrations, users, memberships, secret changes, cloud letters, DNS or deployments were executed. Production JWT and Storage API verification remains gated on release approval. The legacy CV remediation document explicitly identifies unavailable compatibility evidence rather than claiming legacy workflows were tested.

## Live local employer baseline

Run `baseline-2026-10-14-171543-e41dedbc` used this branch's engine with the existing private root `C:\DEV_LOCAL\jobs4jsr`. A SQLite backup was created in ignored worktree `tmp/pre-phase1.sqlite3` first. All enabled sources completed without errors:

| Source | Inspected | Verified in radius | Qualified | Existing duplicates | Newly added |
|---|---:|---:|---:|---:|---:|
| Star Group | 14 | 6 | 6 | 6 | 0 |
| Accor Auckland hotels | 8 | 7 | 4 | 4 | 0 |
| Hind Management / Sudima | 22 | 0 | 0 | 0 | 0 |
| Atomic Coffee Roasters | 3 | 1 | 1 | 1 | 0 |

Catalogue: 11 open qualifying vacancies, three recommendations, no newly added jobs. Hind's zero is a successful feed check, not a source failure. The report is local at `C:\DEV_LOCAL\jobs4jsr\outputs\reports\latest.html`. Existing generated letters were retained; this baseline needed no new letters. Fixture tests separately verify generation for exactly three of eight new baseline jobs and extra letters by local ID.

The pre-existing scheduled row `2026-10-14-scheduled` retained completion `2026-10-14T09:16:20.592279+13:00`. Exported Windows Task XML before/after baseline is identical. The Monday/Wednesday/Friday 09:00 schedule was not reinstalled, triggered or changed. All 22 relative report links resolve to existing local files. Existing job URLs/statuses and application status_history match the pre-baseline SQLite backup exactly. Original candidate files/profile were not rewritten; the additive SQLite upgrade stores catalogue events/UUIDs and sync attempt history.

## Browser validation

The actual Worker login/configuration shell was inspected. An explicitly marked, fictional local preview (no real jobs, personal records or Supabase) was used to exercise the board at 375 and 320 pixel viewport widths. Document widths were 360 and 305 respectively, with no horizontal overflow. All Jobs, Saved, Applied, Dismissed and employer/role/location controls were visible. Dismiss moved the fictional card out of All Jobs; Dismissed displayed it with Restore; Restore removed it from Dismissed and returned it to All Jobs. Source, found/verified dates, match summary and recommendation section were visible. Screenshot evidence is ignored at `tmp/qa/mobile-preview.jpg`.

The mock UI preview does not prove real authentication or deployment. Its in-memory decisions are intentionally disposable; durable decision persistence and publisher isolation are tested in PostgreSQL. Letter download positive/negative paths use mocked upstream responses; real private downloads await approved account and bucket provisioning.
