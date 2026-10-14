# Jobs4JSR: Supabase architecture and reuse review

Assessment date: 14 October 2026. Status: proposal awaiting owner approval.

## Recommendation

Use **Funk My Brand (`qnvihygrnfgpmsznayje`) for Auth, isolated Jobs4JSR tables and private letter Storage**, conditional on security remediation and access tests. Keep the existing Python engine and Windows schedule initially (approach B). Serve a small private board through a dedicated Cloudflare Worker at `jess.maximisedai.com`. Do not port the four adapters to Edge Functions for the first release.

This is the smallest practical reuse of working infrastructure. It does **not** deliver discovery while the local computer is off. If unattended cloud discovery is required, move the same Python engine to an approved, continuously available worker (approach C); a scheduler alone cannot supply that worker. There is no verified suitable existing cloud Python runtime in this assessment. Approach A is feasible after a measured, bounded TypeScript port, but carries greater initial implementation and regression risk.

Do not upload Jess's CVs, profile or letters to the existing CV tables as currently configured. Keep original documents and the canonical candidate profile local, as required by the original privacy brief. Uploading generated letters to private cloud Storage requires an explicit approval of that change in data handling. Neither upload nor any implementation is authorised by this review.

## 1. Scope and evidence

Read-only inspection covered the repository at `C:\DEV_LOCAL\jobs4jsr`, the committed source on [PR #1](https://github.com/captjreacher/jobs4jsr/pull/1), Supabase project/function metadata, deployed function source where retrievable, SQL catalogues, grants, policies, bucket metadata, extension and cron metadata, security advisors, and current official documentation. No CV contents, Storage object contents, application records or credentials are included in this document.

PR #1 is open and unmerged, head `e5b3bfe02e8dfd9c333e357dc372855acc9439b5`, targeting `main`. Its visible check is GitGuardian success; this is not proof of CI adapter tests. Earlier development recorded 34 Python tests, but this assessment does not claim a fresh integration test or cloud deployment. The prior web-board implementation is uncommitted on `codex/private-job-board` and is preserved separately. This review is committed in an isolated worktree; those drafts are not part of the review PR or evidence of production readiness.

Important limitations: `generate-cv` source retrieval failed twice with the connector's internal/unavailable error; its deployment metadata was available. No function was invoked to generate or extract a CV. Auth provider/SMTP/signup/redirect configuration, billing plan and utilisation were not retrievable through the inspected metadata. Anonymous REST access was not exercised against personal records: effective SQL grants and RLS state provide the security evidence below. Data API exposed-schema configuration still needs owner verification.

## 2. Infrastructure inventory

| Component | Observed state | Reuse assessment |
|---|---|---|
| Jobs4JSR engine | Python, requests, SQLite, deterministic scoring and DOCX/Markdown letters; four employer adapters | Retain source parsing, geography, qualification, deduplication and local candidate evidence |
| Local task | `Jobs4JSR Discovery`, Ready; trigger boundary `2026-10-14T09:00:00`, weekday mask 42 = Monday/Wednesday/Friday | Preserve; Windows NZ timezone and local boundary follow DST |
| Funk My Brand | Healthy, Sydney `ap-southeast-2`, PostgreSQL 17.6 | Preferred shared backend; regional proximity and existing identity infrastructure |
| MGRNZ | Healthy, India `ap-south-1`, PostgreSQL 17.6 | Reference patterns only; avoid a second project and cross-project identities |
| FMB profiles | `profiles`, profile data/state/version/events, user roles/entitlements, supporting narratives and narrative templates | Existing identity/profile model is useful, but seeded-public policies and CV domain coupling need care |
| FMB CV tables | `cvs`: user/title/content/style/summary/experience/skills; `cv`: user/raw text/parsed; `cv_files`: CV FK/filename/bytea content | Three overlapping representations; not a single safe canonical profile store |
| FMB Storage | `uploads` private; `deployments` private; `logos` public, 5 MB image MIME restrictions | Private upload folder ownership pattern useful; public logos unsuitable for documents |
| FMB functions | `generate-cv` active v15, gateway JWT verification enabled; `extract-cv` active v20, JWT verification enabled | Optional future CV workflow, not required for discovery or deterministic letters |
| MGRNZ functions | `opportunities` active v66; `opportunity-scenarios` active v22 | Business-opportunity workflow, not job-vacancy adapters |
| Scheduling extensions | FMB: no installed `pg_cron`, `pg_net` or `pgmq`; MGRNZ: `pg_cron` and `pg_net`, no `pgmq` | Availability differs; do not assume FMB is already scheduled |
| MGRNZ cron | `cron.job` returned no jobs; cron timezone GMT, database timezone UTC | Installed scheduling support is not evidence of an active discovery schedule |
| Other MGRNZ queue infrastructure | `paperclip_execution_queue`, `paperclip-queue-worker`, `process-queue`, event routing and opportunity run/candidate tables | Existing business queues are coupled to their own workflows; no reuse without contract review |
| Cloudflare | Existing Maximised AI zone/Worker infrastructure; no `jess.maximisedai.com` custom Worker binding returned | Dedicated Worker avoids changing the apex site's routing; DNS-read API permission unavailable, so DNS readiness remains unverified |

The local task uses an interactive user, StartWhenAvailable, IgnoreNew, a 20-minute limit and two retries five minutes apart in its installation script. It needs the computer on and the user signed in. Python `due_slot` catches up only the latest due slot; it does not burst through every missed run. Manual run IDs are separate from scheduled IDs. This review has not reinstalled or triggered the task.

### Deployed CV extraction

`extract-cv` explicitly verifies the bearer user through Auth `getUser()`, then uses a service-role client to insert into `cv` with that verified user ID. Its input supports pasted text; PDF input returns 400 because PDF extraction is not wired. Its deterministic parser currently emits empty experience and education arrays, which the schema accepts: schema-valid does not mean professionally complete. AI fallback uses `gpt-4o-mini` only when schema validation fails, and sends input text to OpenAI. Thus it cannot replace Jobs4JSR's reviewed CV reconciliation without missing facts, external processing approval and additional tests. Wildcard CORS and detailed error responses also deserve review.

`generate-cv` is deployed but its implementation and ownership enforcement could not be verified. Do not assume JWT gateway verification proves per-user authorisation or output privacy. Obtain source before reuse.

### MGRNZ discovery patterns

The retrieved `opportunities` implementation uses a server-side service-role client and an operator bearer token (or `x-operator-token`), failing closed if the token is missing. It includes bounded result/search-term settings, durable discovery runs/candidates, workflow events and diagnostics, and background execution using `EdgeRuntime.waitUntil`. Its discovery targets business leads through Google Places, with eligibility, enrichment, audit and SMTP outreach workflows. Background execution remains subject to Edge runtime limits; it is not a durable queue by itself.

`opportunity-scenarios` is a token-protected, read-only GET endpoint that calls `opportunity_list_active_scenarios`. It is a scenario registry, not an employer crawler or scheduling worker. Its gateway `verify_jwt=false` is paired with custom operator-token checks; never expose that token to Jess's browser. Reuse the ideas of bounded stages, durable run status and source diagnostics. Do not reuse lead tables, paid Places calls, operator credentials, scoring, or outreach paths for Jobs4JSR. No application submission or email sending belongs in this system.

## 3. Edge discovery feasibility

| Adapter | Current permitted entry point | Edge port considerations |
|---|---|---|
| Star Group | Public employer sitemap and individual advertisements | XML enumeration, JSON-LD parsing, live application check; batch detail requests |
| Accor | Public vacancy sitemap and employer advertisements | Large sitemap (about 2 MB in earlier live check); parse/filter before details, measure CPU and memory |
| Hind / Sudima | Public Workable employer widget feed and vacancy pages | JSON feed is straightforward; Auckland/role filtering still needed; zero qualifying results can be a successful check |
| Atomic Coffee Roasters | Public LiveHire employer cards and advertisement pages | Server-rendered card parsing plus JSON-LD; fixtures needed against HTML changes |

The current client checks robots before following each redirect, honours crawl delay/request rate with a minimum one-second delay, uses 25-second request timeouts, limits redirects, and stops a source on HTTP 429. Robots retrieval failure is closed; missing robots (404) is treated as unrestricted. Discovery catches source failures separately and records inspected/verified/qualified/duplicates/errors and last success. These rules must survive any port. Robots permission is necessary but does not override employer terms; periodically recheck both. Do not substitute restricted SEEK, Indeed or Trade Me scraping.

Supabase supports outbound HTTPS and async waits, so these public feeds and pages are technically suitable. Python's requests, HTMLParser, SQLite and python-docx are not a direct Deno deployment: the transport, robots parser, extraction, persistence and document production need a deliberate port or separate Python worker. Browser automation is unnecessary for these four current entry points.

Hosted Edge limits are 256 MB memory, two seconds CPU per request, 150 seconds wall time on Free or 400 on paid, and a 150-second request idle timeout. Async I/O does not count toward CPU, but waiting for robots pacing counts toward wall time. A sequence of detail requests plus slow 25-second timeouts can exceed the budget. A fast prior local run does not prove Edge suitability. Use one bounded source/page batch per invocation, persisted cursor, aggregate deadline, per-host shared pacing/lease, bounded retry with Retry-After and jitter, and per-source failure records. Parallel source workers must not bypass shared rate limits. Return an accepted run promptly, then persist each stage; `waitUntil` does not remove resource limits. See [official limits](https://supabase.com/docs/guides/functions/limits).

## 4. Architecture comparison

| Criterion | A: Edge discovery | B: Local Python + sync | C: Cloud orchestration + Python worker |
|---|---|---|---|
| Reliability | Cloud triggers; short bounded batches, checkpoints/retries essential | Proven engine; PC, login, network and runtime remain dependencies | Independent of Jess's PC only if worker is continuously available; leases/retries required |
| Complexity | Highest initial port/testing effort for four parsers, robots and DOCX | Lowest: add safe export/sync and board | Medium/high: worker packaging, durable work claiming and monitoring |
| Cost | Small invocation demand; existing plan may suffice | Existing local hardware plus existing backend capacity | Backend plus approved worker hosting; no hosting price assumed |
| Maintenance | TypeScript adapter parity and dependency audits | One Python adapter implementation retained | Same Python adapters, additional worker operations |
| Dependencies | Deno Edge, cron/pg_net, database/Storage, Python alternative for letters or TS DOCX | Windows task, Python, SQLite, Supabase, Cloudflare | Supabase scheduler/queue, Python runtime host, network, Cloudflare |
| Privacy | Candidate processing moves to cloud unless letters stay local | CV/profile stay local, only reviewed projection and letters sync | Candidate evidence would need secure worker provisioning and explicit approval |

Choose B for the first approved implementation. Choose C if cloud availability is a hard requirement and an existing trusted worker can be identified. Choose A only after fixture parity and Edge CPU/wall-time measurements demonstrate safe limits. Avoid introducing Redis, vector storage, Google Places, paid AI or a second Supabase project for a single private board.

## 5. Security findings and proposed remediation

**High-priority gate:** SQL catalogues confirm `cv`, `cvs`, `cv_files` have `relrowsecurity=false`, and effective `anon` SELECT/INSERT plus authenticated SELECT privileges. In an exposed schema these permit unscoped access through the Data API. The existing owner policy on `cvs` is inactive. `cv_files.content` stores raw bytes, so this is not merely metadata exposure. No personal rows were read to demonstrate it. Revoke unnecessary anonymous grants, enable RLS and create tested ownership policies before reuse. For `cv_files`, ownership must traverse its parent `cv.user_id`; it has no independent user column. Audit UPDATE/DELETE/TRUNCATE and inherited/default grants too: RLS does not protect TRUNCATE. Use a staged migration, compatibility tests and rollback plan rather than blindly enabling RLS on every legacy table.

Other FMB advisor findings include two policies on RLS-disabled tables, seven public tables flagged without RLS, two definer views, 27 mutable function search paths, 19 anonymous-executable definer functions, 36 authenticated-executable definer functions, and disabled leaked-password protection. These counts describe advisor findings, not confirmed exploits. Several public administrative SECURITY DEFINER functions are executable by anon; their bodies and internal role checks were not audited here. Review execution grants, fixed search paths, auth checks and views before admitting another private-data application. [RLS remediation](https://supabase.com/docs/guides/database/database-linter?lint=0013_rls_disabled_in_public), [inactive-policy remediation](https://supabase.com/docs/guides/database/database-linter?lint=0007_policy_exists_rls_disabled), [definer-view remediation](https://supabase.com/docs/guides/database/database-linter?lint=0010_security_definer_view).

`profiles` has both id-based and user_id-based ownership policies plus `is_seeded=true` public SELECT. `supporting_narratives` has owner policies and seeded-public SELECT. Permissive policies combine with OR; a new private policy cannot cancel an existing public policy. Never mark Jess's profile/narratives seeded. Resolve the two ownership conventions before mapping records. Reusing these tables is optional and brings versioning/entitlement/domain coupling; the minimal board does not need to write them.

Private `uploads` policies scope paths to the first folder equal to `auth.uid()`. This is a useful pattern, but a sync user writing for Jess needs a separate, explicit entitlement rather than broad authenticated access. `logos` is public and authenticated users can upload/update/delete across that bucket; never use it for letters. `deployments` is private with no matching object policies in the inspected policy inventory; do not infer usability just from its private flag.

Proposed board controls:

- Dedicated `jobs4jsr_*` tables with RLS enabled from creation, explicit least-privilege grants, owner membership managed only by administrators, no anonymous access. Use immutable Auth user IDs, not emails or user-editable metadata, for authorisation.
- Dedicated private letter bucket; owner/entitlement checks on bucket AND path. Reader can retrieve only their letters; sync account can publish only assigned owner's vacancy projection and letters. Composite job/owner relationship prevents attaching another user's letter or decision.
- Never put a service-role key in a browser. Prefer a narrowly entitled machine Auth account for sync. A service-role implementation would have project-wide bypass and a larger compromise impact; avoid it for this small publisher.
- Worker verifies a current Auth user and Jobs4JSR membership on requests; existing FMB login alone does not admit every FMB customer to Jess's board. HttpOnly/Secure/SameSite cookies, CSRF origin checks, no-store responses and no private response caching. Serve letters through authorised download or short-lived signed URLs; signed URLs are bearer access until expiry.
- Disable board signup; invite approved users. Do not change project-wide signup/OAuth settings without examining effects on FMB. Verify SMTP/reset flows, redirects, session revocation, MFA option and login throttling before rollout.
- Test anonymous, unrelated authenticated user, Jess, authorised reviewer, and publisher across tables, RPCs and Storage. Include forged ownership, traversal, direct Data API access, seeded flags and sync attempting to overwrite decisions. Validate grants separately from RLS. See [API security](https://supabase.com/docs/guides/api/securing-your-api).

No existing policy, credential or bucket was modified during this assessment.

## 6. Minimal data flow and scheduling design

1. Preserve local reviewed CV/profile/templates as the authority for candidate facts and deterministic letters.
2. Python discovers all qualifying current vacancies inside the existing 10 km Haversine boundary centred at latitude -36.8485, longitude 174.7633 near Queen Street. Unknown work location remains uncertain rather than being guessed as CBD.
3. Keep canonical ad/application URLs and employer/title/location deduplication, with stable IDs and source aliases. A relisted page is not automatically a new vacancy; retain original first-found date and distinguish genuinely new requisitions.
4. Add an **uncapped baseline** catalogue scan after approval. Existing PR #1 initial/scheduled caps are not a complete baseline. Incremental scans retain all qualifying jobs; the maximum three controls new recommendations/letters highlighted per scheduled run, not the entire visible board. Explicitly approve whether letters are generated for every baseline vacancy or queued progressively.
5. Publish a minimal vacancy projection, source-check/run diagnostics and authorised letters with idempotent upserts, stable IDs and content hashes. Use an outbox/retry checkpoint: failed sync must not erase the local results or rerun completed discovery. Never upload entire SQLite databases or CV evidence by accident.
6. Supabase stores vacancy facts separately from Jess's Save/Dismiss/Applied decisions. Sync can update source facts but cannot overwrite decisions. A single job can be Saved and Applied; Dismiss is reversible. Preserve historical status/events and migrate existing application history only through an approved reconciliation.
7. Cloudflare serves the board and authenticated APIs. All qualifying catalogue rows are available with filters; top-three recommendations are a separate view. Distinguish active, closed and verification-unknown. Missing from a feed or a failed source check is not proof of closure. Show last verified and source health; never show stale checks as fresh.

For B, retain Monday/Wednesday/Friday 09:00 `Pacific/Auckland`, including DST and existing latest-slot catch-up. A stale last-success indicator makes the local dependency visible. Manual/baseline/sync operations must not consume the next scheduled slot.

For future A/C, use a distinct due-slot ledger with a unique local-date/run-kind key, transactional claim lease, heartbeat/expiry, bounded retries and per-source stage checkpoints. The inspected MGRNZ cron timezone is GMT: a fixed UTC M/W/F expression will get NZ weekday/time wrong around DST. Prefer an hourly UTC tick with an IANA `Pacific/Auckland` due-slot calculation, accepting only due weekday slots, and catch up the latest missed slot. Store secrets in Vault/server configuration and authenticate invocation; official scheduling uses pg_cron plus pg_net ([guide](https://supabase.com/docs/guides/functions/schedule-functions)). Do not run local and cloud schedulers as competing owners; any transition needs shared idempotency and an explicit cutover. No cloud schedule exists for Jobs4JSR today.

## 7. Estimated operational costs

Estimates are USD, exclude tax/FX, existing subscriptions, electricity and owner time. Actual project plans and shared quota usage were not verified.

| Item | Expected small-board cost | Conditions |
|---|---|---|
| Existing FMB Auth/Postgres/Storage | Approximately $0 incremental within current quotas | Shared workloads may already consume quotas; no new project required |
| Supabase plan if upgrade necessary | Pro starts $25/month, first project included; additional project compute starts $10/month | Not an instruction to upgrade or a verified current bill |
| Cloudflare private-board Worker | Free may suffice; paid Workers starts $5/month if needed | Free request allowance 100,000/day and 10 ms CPU/request; test actual board requests |
| Local Python discovery | No job-search/AI API charge | PC/network availability and maintenance remain costs |
| Cloud worker under C | Undetermined | Reuse approved existing runtime if possible; price hosting only after choosing it |
| Optional existing CV AI functions | Usage-dependent extra AI charges | Excluded from recommended flow; secrets, balance and privacy approval not verified |

At three scheduled runs/week there are roughly 13 run slots/month. Even four source invocations per slot plus retries are small compared with Supabase's Free 500,000 invocation allowance; storage/egress and other project activity still matter. Budget, for example, 1,000 letters at 100 KB each as about 100 MB before versions; this is an estimate, not a measured average. Free Supabase lists 500 MB database, 1 GB Storage and inactivity pausing after one week. Monitor quota and backup needs rather than assuming free service guarantees availability. Sources: [Supabase pricing](https://supabase.com/pricing), [Workers pricing](https://developers.cloudflare.com/workers/platform/pricing/).

## 8. Proposed implementation phases (approval required)

1. **Security and contracts:** obtain unavailable function source; confirm Data API schemas, grants, definer functions, Auth settings and billing. Approve isolated board schema, letter upload privacy, authorised users and remediation of legacy CV access. Test legacy FMB compatibility in a safe environment.
2. **Local completeness:** finish/review uncapped baseline, lifecycle rechecking and recommendation separation; preserve existing SQLite/history/task and four adapter fixtures. Verify failure isolation, deduplication, relative reports and scheduled idempotency.
3. **Private backend:** reviewed migrations for membership, vacancies, source checks/runs, decisions and private bucket. Run positive/negative access tests using real JWT roles; SQL metadata alone is insufficient deployment validation.
4. **Sync and Worker:** idempotent publisher/outbox, private login, Save/Dismiss/Applied, authenticated letters and stale-source display. Test mobile views, CSRF, session expiry, downloads, unavailable backend and decision preservation. Keep preview private.
5. **Controlled launch:** separate owner approval for migration, accounts, secrets, custom domain/DNS and deployment. Verify Jess's access and anonymous denial, then monitor local schedule and sync. No automated applications or emails.
6. **Optional cloud discovery:** only if requested; evaluate an existing Python worker first. Prove DST, catch-up, crash recovery, lease expiry and duplicate scheduler protection before changing the Windows task. An Edge port requires fixture parity and measured resource budgets.

## 9. Risks and unresolved decisions

- Legacy CV grants/RLS are an immediate privacy blocker for direct reuse; shared project administrator/service-role access means logical isolation is not a separate security boundary.
- `generate-cv` source is unavailable through the connector; extraction is incomplete and may invoke external AI. Neither is approved as candidate truth or required for letters.
- FMB's seeded-public profiles, subscriptions, onboarding and domain assumptions can create accidental coupling. Use Auth identity without inheriting unrelated entitlement or publishing behaviour.
- Auth provider configuration, signup, SMTP, project bill/quotas, exposed schemas and full privileged-function behaviour remain unverified. Review these before implementation approval.
- Choose authorised viewers and account recovery method. Existing project users must not automatically gain access.
- Confirm approval to upload private generated letters, retention/deletion policy and backup/export arrangements. Original documents/profile remain local by default.
- Decide whether PC-dependent discovery is acceptable. No confirmed cloud Python runtime or Jobs4JSR cloud schedule exists. A new hosting service is not included in the minimal recommendation.
- Confirm complete-baseline letter policy and full-catalogue versus three-new-recommendation semantics. Never drop qualifying catalogue jobs to satisfy a presentation cap.
- Employer markup, robots, terms and cloud IP blocking can change. Every run must preserve source errors and uncertainty rather than fabricate results or infer closure from outage.
- Cloudflare custom domain binding is not present in inspected metadata; DNS configuration could not be authoritatively inspected with available permissions.
- PR #1 is still unmerged. This documentation PR intentionally builds on its adapter code and should not be treated as approval to merge or deploy either PR. The current uncommitted board draft is outside this review's delivery.

Owner approval is required before any implementation, database migration, account/credential change, upload, deployment or scheduling alteration. This deliverable changes documentation only.
