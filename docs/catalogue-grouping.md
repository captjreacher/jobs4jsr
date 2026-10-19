# Catalogue grouping review

Implemented locally; no production SQL, merge or deployment performed.

## Model inspected

Read-only inspection of the `funk-my-brand` Supabase project confirmed that
`jobs4jsr_jobs` contains `id`, `owner_id`, `vacancy` JSONB and `letters` JSONB.
`jobs4jsr_decisions` contains only `job_id`, `owner_id`, `saved`, `dismissed`,
and `applied`. There is no persistent viewed/seen field.

`src/jobs4jsr/catalogue.py` sets `vacancy.found` to the original discovery's
calendar date (YYYY-MM-DD), preserves it on rediscovery, and sets `is_new`
according to discovery run. `last_seen_run` refers to discovery verification,
not Jess's viewing activity. Neither flag establishes that Jess has read a job.

## Proposed additive SQL — requires review before production

`supabase/optional/jobs4jsr_seen_review.sql` adds nullable `seen_at timestamptz`
to the existing decisions table. It is outside the automatic base migration
directory. No backfill, defaults, policy changes or historical decision updates.
The existing reader/owner SELECT, INSERT and UPDATE policies and composite
job/owner foreign key remain in force. Sync users cannot write decisions.
Local PostgreSQL tests apply this proposal and exercise the existing RLS.

Review and authorise this SQL before any production application. Apply the
reviewed column change before releasing the UI/Worker together. The current
release depends on the new column to persist viewing state; do not deploy it
alone. No production change was made during this task.

## Behaviour

- A job becomes seen after at least 50% of its catalogue card is continuously
  visible for one second while the document is visible. Hidden/collapsed cards
  and recommendation summaries do not mark jobs seen. Backgrounding the page
  cancels pending timers; returning starts a new observation period.
- The authenticated, same-origin Worker records server time. It inserts a
  missing decision row without replacing existing rows, then PATCHes only
  `seen_at`, only where it is null. Existing decision actions continue to PATCH
  only their selected flag. Legacy Applied status remains preserved.
- Failed seen writes do not mark the job seen persistently. A later observation
  or visit can retry. No viewing state is inferred from Saved/Applied flags.
- Classification stays stable during the current signed-in page visit, including
  action refreshes. Reloading or signing out/in reads persisted seen state.
- On initial rollout, historical viewing is unknown, so existing jobs are NEW
  until actually observed. This deliberately avoids inventing historical state.
- Existing filters and tab selection run first. Each resulting job goes to one
  section: unseen → NEW; seen with a discovery date from today through exactly
  seven calendar days ago → RECENT; other seen jobs → EARLIER OPPORTUNITIES.
  Calendar days and update copy use Pacific/Auckland. Missing/invalid discovery
  dates go to EARLIER once seen. Existing closed-advert and dismissed visibility
  behaviour is retained; this change adds no new vacancy-state exclusion.
- NEW and RECENT start open; EARLIER starts closed. Native details/summary
  supplies keyboard operation and expanded state. Choices persist across
  filters/actions for this visit. Headers have a minimum 52px touch target.
- Top recommendations stays separate. Cards, score calculations, authentication,
  sync payloads and mobile grid breakpoints are retained. Health API diagnostics
  remain available; the visible board shows only readable update timing.

## Verification

- `npm test`: grouping precedence, inclusive seven-day boundary, earlier/unknown
  dates, exclusive membership, filters and decision views, accordion defaults,
  Auckland update dates, Worker first-seen PATCH and existing auth/RLS coverage.
- `.\.venv\Scripts\python.exe -m unittest discover -s tests -v`: 46 passed.
- `npm run package`: Wrangler dry-run packaging passed; no deployment.
- `npm run preview`, then `npm run test:ui`: Edge headless at 1280×900 and
  390×900, with isolated fictional API fixtures. Checks native accordion defaults,
  touch targets, overflow, accordion state through rerenders, visibility-based
  seen writes, stable NEW during the visit, fresh-visit classification and
  Save/Applied/Dismiss/Restore. No production login or writes.
  Playwright must be installed or provided through the `PLAYWRIGHT_MODULE`
  environment variable (a module URL). Screenshots are written under ignored
  `tmp/catalogue-evidence/1280.png` and `390.png`.

## Release approval review

See [catalogue-release-review.md](catalogue-release-review.md) for the live
11-job snapshot, PASS/WARNING results, strengthened tests and the exact
migration/merge/deployment/rollback sequence. No production change is authorised.
