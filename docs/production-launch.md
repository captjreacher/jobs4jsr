# Jobs4JSR production launch — 14 October 2026

**Current canonical URL:** https://jess.funkmybrand.com. The original hostname below now redirects; see [completed hostname migration](hostname-migration.md). Original launch versions and URLs are retained as historical evidence.

Owner explicitly authorised the base production launch and **waived the verified-backup gate for this release**. This is accepted owner risk, not evidence that Funk My Brand is recoverable. No recovery investigations or additional readiness PRs were opened. The earlier NO-GO gate was superseded by this explicit waiver; recovery remains NOT VERIFIED.

## Applied release

Started from merged main `f591241` including PR #6. Existing approved Supabase CLI runner selected and applied only `20261014034534_jobs4jsr_private_board.sql` then `20261014041250_jobs4jsr_health.sql` to `qnvihygrnfgpmsznayje`. Both versions are recorded in the migration ledger. Six Jobs4JSR tables exist, all have RLS enabled, anon SELECT is false on all six, and 16 policies are present. The public table grants/policies are the reviewed implementation. No optional Storage SQL was run, no letter bucket was created, and no legacy CV table/security or Auth configuration was changed.

Jess's reader account and a dedicated machine Auth account were provisioned using existing FMB administrator credentials. Reader and sync memberships have the reviewed least-privilege separation. Existing Auth provisioning triggers/default profile, subscription and entitlement side effects were retained. Machine credentials are in the ignored local `.env`; only the publishable key and immutable Jess UUID are Worker secret bindings. No service-role key is in the publisher, Worker or frontend. Local access files have Windows ACLs restricted to the current owner.

The existing Python publisher synchronised **11 catalogue vacancies, all marked open**, and discovery/source health. The three stored recommendations are displayed separately. These are the existing qualifying catalogue, last verified on the same NZ date; no new discovery or scheduled slot was consumed. Every original advertisement URL returned HTTP 200 in a single-request launch link check. HTTP success alone is not a fresh full vacancy-qualification scan.

Cloudflare Worker: **jobs4jsr-board**, Static Assets, `workers_dev=false`, no cron. Live Custom Domain: **https://jess.maximisedai.com**. Current deployed version after secure binding configuration: **d3ac4ce4-df09-4c32-a544-096d99b449c6** (100%). Initial code/assets deployment: `8bedb006-da9e-4850-9feb-7c7edc4363c2`. Existing Wrangler OAuth infrastructure was reused. DNS-list API permission was denied, but public DNS had no Jess record before binding and the Worker domain inventory had no Jess assignment. Custom Domain creation succeeded without conflict; public DNS now resolves, HTTPS serves this board, and the domain API maps the hostname to this Worker. All earlier Worker-domain assignments and zone routes were checked unchanged.

## Short production smoke evidence

- Private login succeeds in the live browser and API; catalogue and source health load.
- Anonymous API returns 401; authenticated machine account board login returns 403.
- Save, Dismiss, Applied and Restore persist across subsequent reads. The temporary test decision was removed afterward, leaving no false application state.
- Dedicated publisher cannot insert reader decisions (403).
- Eleven catalogue entries and exactly three recommendations are visible; all hosted letter metadata is empty.
- All eleven original advertisement links return 200.
- Authenticated mobile layout checked at 390×844: two-column filters, single-column cards, visible recommendation section, no elements overflowing the viewport.
- DNS A records resolve and HTTPS serves the Jobs4JSR Worker.

Ignored audit evidence: `tmp/launch/smoke.json`, `links.json`, browser screenshots and deployment CLI output observed during launch. No complete development suite or full preflight was repeated. Original 27 private hashes and all rows in `jobs`, `runs`, `status_history` match the prior preservation snapshot. Only publisher sync audit rows were appended locally. Named stash is retained and Windows task XML is identical: M/W/F 09:00 Pacific/Auckland. Its existing automatic publisher hook now uses configured private credentials; task definition is unchanged.

## Access and remaining limitations

Jess's initial login details are stored only in `data/private/board-access.txt`, with an owner-only ACL. They were not emailed or placed in Git. Keep the file private. Existing global Auth recovery/mail configuration was not modified; self-service recovery is not implemented in this board. The sync password and administrator key must never be shared with Jess or published.

`JOBS4JSR_LETTER_UPLOAD_APPROVED=false`. Original CVs and letters were not uploaded; hosted letters and cloud discovery remain separate enhancements. Local discovery still needs the Windows computer/runtime available. Backup recoverability remains unverified under the accepted waiver, and legacy CV security findings remain outside this launch scope. No unrelated infrastructure changes were made.

For an incident, disable only Jobs4JSR publication locally and revoke its memberships through the approved administrator if necessary. Roll back this Worker's deployment with the existing Wrangler deployment tooling; all earlier versions are retained, although this is the first complete application launch. Remove only this new domain assignment if taking the site offline. Leave additive tables/history intact during triage; database cleanup or shared-project restore requires a separate owner decision.
