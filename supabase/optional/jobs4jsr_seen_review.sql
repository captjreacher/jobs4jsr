-- REVIEW ONLY. Do not apply to production until reviewed and authorised.
-- No backfill: historical viewing state is unknown.
-- Existing decisions SELECT/INSERT/UPDATE owner + reader RLS remains in force.
alter table public.jobs4jsr_decisions add column seen_at timestamptz;
