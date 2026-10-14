# Canonical hostname and branding migration

Completed 14 October 2026 under explicit owner authorisation. Canonical application: **https://jess.funkmybrand.com**. This updates the existing application, not its backend, users or catalogue.

## Infrastructure

- Existing Worker: `jobs4jsr-board`; previous deployed version `d3ac4ce4-df09-4c32-a544-096d99b449c6`.
- Transition version `90b18a5e-c4dc-4e0f-85c3-4d23d3c610cb` kept both hostnames active while the new host was tested.
- Final deployed version `57147c16-b01c-4a46-8e97-130271c2a6e3` serves the canonical board and redirects the old host.
- Existing account `f16286e0cc21b0fb60a275765b8ca576`; Funk My Brand zone `defb6ae446711bdb813725864d60d22d`.
- Both exact Custom Domains bind to the same Worker. No other Worker/project, zone-wide redirect or shared Worker change was introduced. All prior custom-domain assignments remained unchanged.
- Public DNS initially had no new Jess record, and Worker-domain inventory had no assignment. The existing OAuth token cannot list DNS records (API 10000). Custom Domain creation nevertheless succeeded without conflict; A records now resolve and HTTPS certificate validation succeeds. Domain metadata reports enabled, mapping to the existing Worker, certificate `77fba89a-4583-469e-bb80-fddb9b7e80e6`.

`wrangler.json` retains Static Assets, `workers_dev=false`, existing Supabase URL, and both Custom Domain routes. `LEGACY_REDIRECT_ENABLED=true` retires the old application on the existing Worker. `CANONICAL_HOST` records the approved production hostname; redirect destination is fixed in code to avoid an arbitrary-host redirect. Wrangler secrets `JESS_USER_ID` and `SUPABASE_PUBLISHABLE_KEY` were retained without rewriting them. No credentials were committed or exposed in assets.

## Auth and security

Supabase project remains `qnvihygrnfgpmsznayje`. Inspected Auth site URL is `https://app.funkmybrand.com`; redirect allowlist is `https://funkmybrand.com/**,https://app.funkmybrand.com/**,http://localhost:5173/**`. They were **not changed**: this board uses the password grant via its own server endpoint and has no OAuth callback, invitation or password-recovery redirect flow. Future implementation of those flows will need an independently reviewed exact-host Auth allowlist entry; do not broaden global settings for this migration.

CSP and navigation use same-origin relative URLs and need no host-specific change. CSRF still requires the exact request origin; old-origin writes to the new host are denied. Secure, HttpOnly, SameSite=Strict, host-only cookies and membership verification are preserved. Jess signs in on the new hostname with the same email and password. No users, passwords, memberships, vacancy records or discovery schedule were migrated/reset.

On the old hostname, GET/HEAD return permanent 301 redirects with safe paths/query strings. Queries containing authentication parameter names or JWT/Bearer values are dropped, and an explicit empty fragment prevents inheriting old OAuth fragments. Access/refresh cookies for the old host are expired. Cookies/tokens are never forwarded to the new hostname. POST and other writes return 409 with the new address rather than redirecting credential bodies. An old open session must navigate to the new site and sign in there; the old host no longer serves an independent active application.

## Branding and verification

Login uses the approved Funk My Brand header, subtitle, eyebrow, heading and description. The existing pink-gradient favicon/logo from `funkmyfans/apps/creator-cockpit/public/favicon.svg` is reused with pink accents. The real form, authentication and responsive job board remain intact.

Focused verification: **13 tests pass** (three new hostname/redirect tests plus ten existing Worker behaviour tests). Live HTTPS, same-account login, all **11 vacancies**, three recommendations, anonymous/non-reader denial, cross-origin rejection, and Save/Dismiss/Applied/Restore persistence pass. The temporary smoke decision was restored exactly; read-only hashes for all six board tables match the captured pre-test snapshot. No catalogue publication was rerun. Authenticated mobile layout at 390×844 shows all controls without horizontal overflow. Browser login/board screenshots are ignored under `tmp/launch`.

Live old-host checks confirm 301 root, safe query/path preservation, token-query stripping, and refusal to redirect POST bodies. Final custom-domain metadata confirms both domains map to the same Worker and unrelated assignments remain intact. Existing private-file hashes and Windows task XML are unchanged; hosted-letter uploads remain disabled. No backend migrations or account provisioning occurred.

## Operation and rollback

Use the new canonical URL and the existing Jess credentials. Existing publisher configuration and M/W/F 09:00 Pacific/Auckland discovery are unchanged. Deploy with `npx wrangler deploy` from this repository using existing approved credentials; do not create a second Worker or change secrets. Keep both Custom Domain routes so the old hostname redirects.

For transition rollback, set only `LEGACY_REDIRECT_ENABLED=false` and redeploy this Worker to restore old-host operation while retaining the new binding. Existing Worker versions are retained for code rollback. Do not alter the shared Supabase Auth site URL or unrelated domain routes. No outstanding functional blocker was found; DNS-record listing remains unavailable through the current token, while binding, DNS resolution and TLS are verified independently.
