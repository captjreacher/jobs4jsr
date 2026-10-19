# Catalogue release recovery — 20 October 2026

The previous live smoke test incorrectly required recommendations > 0. The
catalogue actually has zero eligible recommendations. PR #7's job grouping and
the already-applied `20261019114740_jobs4jsr_seen_at` migration remain valid.
Production was restored to Worker `068927c5-f599-4ff4-a8ea-944713eb370a`.

The recovery adds a quiet empty recommendation message, unit cases for zero,
one and multiple recommendations, and a shared DOM assertion used by local and
production tests. Recommendations must match eligible filtered source data;
catalogue IDs/counts are independently checked, including all 11 original jobs.
No migration or sourcing/scheduling changes are part of this correction.

## Validation and controlled live checks

Run `npm test`, Python unittest discovery, `npm run test:ui` with a running
local preview and Playwright, `npm run package`, and `git diff --check` before
merging/deploying. The UI suite checks 0/1/3 recommendations at desktop and
mobile widths. At recovery preparation: 29 Node and 46 Python tests passed.

Before deployment, confirm the captured Worker version is active and the tracked
migration exists once with nullable timestamptz/no default. Do not reapply SQL.
Capture original job hashes, all genuine decisions/seen timestamps and scheduled
task XML. Deploy only a clean merged recovery commit with `--keep-vars`.

Use `scripts/test-board-production.mjs` only with explicit release-test approval.
It reads an ignored JSON config through `JOBS4JSR_TEST_CONFIG` containing origin,
fixtureId, fixtureEmployer, cookiesPath and output. Set
`JOBS4JSR_PRODUCTION_TEST_APPROVED=true` and provide Playwright normally or through
`PLAYWRIGHT_MODULE`. Credentials/session files remain ignored and private.

The operator creates one UUID-specific, clearly labelled synthetic QA job plus
its decision row, initially dismissed and not recommended. Its vacancy contains
a unique `release_fixture` marker. This keeps it out of the default catalogue
of 11 genuine jobs. No real job is marked Applied or has its seen state reset.
The test suppresses its own automatic seen requests for genuine jobs, allowing
real production seen requests only for the QA fixture. Other genuine user
sessions and their history remain unaffected.

Actual authenticated UI/API checks cover both viewport sizes, filters, tabs,
accordion counts/defaults/keyboard, empty recommendations, 11 genuine jobs,
Save/Unsave/Applied/Dismiss/Restore on the fixture, first-seen timestamp stability
and correct grouping after a fresh visit. Anonymous login/API access and the
existing sync identity's inability to access Jess's board are also checked.

After closing the test browser, remove only the synthetic decision/job with
guards matching both its exact UUID and unique vacancy marker, in one
transaction. Cleanup is required on failure too. Compare all genuine rows and
timestamps with the snapshot; confirm 11 jobs, no duplicates, unchanged RLS,
one migration entry and unchanged scheduling. Never bulk-clear seen timestamps,
backfill jobs or restore an old database over genuine user activity.

On a genuine acceptance failure, clean up only the fixture and restore the
captured Worker version. Keep the existing additive migration in place. Save
the final deployment/verification audit under ignored release evidence.
