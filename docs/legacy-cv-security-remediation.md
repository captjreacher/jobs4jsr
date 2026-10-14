# Legacy CV security remediation proposal

Separate proposal only. Do not execute permissions changes with the Jobs4JSR migrations. The board does not use `cv`, `cvs` or `cv_files`.

The architecture assessment confirmed RLS disabled and effective anonymous read/insert grants on these tables. `cvs` already has an owner policy that is inactive. `cv_files` contains raw bytes and has a parent `cv_id`, not its own user column. See the architecture review for full evidence and advisory links. This exposure should be resolved, but shared FMB compatibility must be proven first.

## Compatibility matrix

| Path | Current dependency | Test required before permission change |
|---|---|---|
| `extract-cv` | Verifies JWT, then service-role insert into `cv` with verified user ID | Existing authenticated pasted-text extraction still succeeds; stored owner equals caller; anonymous request denied; no CV body logged |
| `generate-cv` | Active function, implementation unavailable in assessment | Obtain deployed source; inspect identity/ownership and whether it reads `cvs`/`cv`/`cv_files`; test real existing workflow in staging |
| Frontend CV listing/edit/download | Ownership and callers not fully mapped | User A lists/edits/downloads A only; user B and anon cannot access A; existing create/update/delete paths preserved |
| `cv_files` join | Parent ownership through `cv.user_id` | Missing/wrong parent denied; parent change cannot transfer access; legitimate attachments read correctly |
| Definer RPCs/views | Can bypass RLS depending on privileges/body | Audit invoker/definer grants, fixed search_path and internal owner/admin checks; tests for privilege escalation and unscoped exports |
| Service-role workers | Bypass RLS | Explicit user scope, bounded access and secret handling verified independently of table policies |

## Proposed staged remediation

1. Inventory exposed schemas, effective grants including inherited/default privileges, policy definitions, FK actions, views and RPC callers. Snapshot these definitions privately. Inspect `generate-cv` source before declaring compatibility. Record intended legitimate access per operation.
2. Build disposable local/staging fixtures with two users and synthetic CV/file rows. Capture existing authorised workflow expectations; do not copy production CVs. Test policies and grants with real Auth/API boundaries where available.
3. Prepare a **separate reviewed migration**: revoke unnecessary anon and PUBLIC table privileges; remove broad non-row operations such as TRUNCATE from application roles; enable RLS; restrict owner SELECT/INSERT/UPDATE/DELETE on `cv` and `cvs` with both USING and WITH CHECK as appropriate. Protect `cv_files` through an ownership EXISTS join to its parent. Minimise grants per actual workflow. Do not infer that creating a policy alone protects a disabled-RLS table.
4. Review seeded-public profile/narrative policies and administrative definer RPCs separately: permissive policies OR together; an additional owner policy cannot override an existing public policy. Keep Jobs4JSR out of those data paths.
5. Owner reviews staging compatibility evidence and rollback before approving production permissions. Apply during a monitored window, rerun positive/negative tests and advisors, watch existing FMB errors and document outcomes.

This proposal has **not been compatibility-tested against legacy application workflows**: required deployed function source and production/staging access are unavailable or unapproved. The board's isolated RLS tests do not certify legacy remediation. No legacy SQL migration is delivered or applied; implementation waits for that evidence and separate owner approval.

## Rollback constraints

Preserve schema/grant/policy snapshots and backup data before rollout. Diagnose ownership or missing-operation errors rather than immediately restoring public access. If rollback is necessary, use the owner-approved snapshot and understand that restoring old anonymous grants/RLS-disabled state reopens the known privacy risk. Prefer temporarily disabling the affected CV endpoint over exposing documents. No credential rotation, data deletion or shared Auth changes are authorised by this plan.
