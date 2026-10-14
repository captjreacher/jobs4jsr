-- Isolated discovery health; no legacy CV schema or permissions changed.
create table public.jobs4jsr_runs (
 id text primary key, owner_id uuid not null references auth.users(id),
 started timestamptz not null, completed timestamptz,
 diagnostics jsonb not null default '[]', unique(id,owner_id)
);
create table public.jobs4jsr_source_checks (
 run_id text not null, source text not null, owner_id uuid not null,
 payload jsonb not null, primary key(run_id,source),
 foreign key(run_id,owner_id) references public.jobs4jsr_runs(id,owner_id)
);
create table public.jobs4jsr_sync_health (
 owner_id uuid primary key references auth.users(id), last_successful_sync timestamptz not null
);
alter table public.jobs4jsr_runs enable row level security;
alter table public.jobs4jsr_source_checks enable row level security;
alter table public.jobs4jsr_sync_health enable row level security;
revoke all on public.jobs4jsr_runs, public.jobs4jsr_source_checks, public.jobs4jsr_sync_health from public,anon,authenticated;
grant select,insert,update on public.jobs4jsr_runs, public.jobs4jsr_source_checks, public.jobs4jsr_sync_health to authenticated;
create policy runs_read on public.jobs4jsr_runs for select to authenticated using(exists(select 1 from public.jobs4jsr_members m where m.user_id=(select auth.uid()) and m.owner_id=jobs4jsr_runs.owner_id));
create policy runs_publish on public.jobs4jsr_runs for insert to authenticated with check(exists(select 1 from public.jobs4jsr_members m where m.user_id=(select auth.uid()) and m.owner_id=jobs4jsr_runs.owner_id and m.kind='sync'));
create policy runs_update on public.jobs4jsr_runs for update to authenticated using(exists(select 1 from public.jobs4jsr_members m where m.user_id=(select auth.uid()) and m.owner_id=jobs4jsr_runs.owner_id and m.kind='sync')) with check(exists(select 1 from public.jobs4jsr_members m where m.user_id=(select auth.uid()) and m.owner_id=jobs4jsr_runs.owner_id and m.kind='sync'));
create policy checks_read on public.jobs4jsr_source_checks for select to authenticated using(exists(select 1 from public.jobs4jsr_members m where m.user_id=(select auth.uid()) and m.owner_id=jobs4jsr_source_checks.owner_id));
create policy checks_publish on public.jobs4jsr_source_checks for insert to authenticated with check(exists(select 1 from public.jobs4jsr_members m where m.user_id=(select auth.uid()) and m.owner_id=jobs4jsr_source_checks.owner_id and m.kind='sync'));
create policy checks_update on public.jobs4jsr_source_checks for update to authenticated using(exists(select 1 from public.jobs4jsr_members m where m.user_id=(select auth.uid()) and m.owner_id=jobs4jsr_source_checks.owner_id and m.kind='sync')) with check(exists(select 1 from public.jobs4jsr_members m where m.user_id=(select auth.uid()) and m.owner_id=jobs4jsr_source_checks.owner_id and m.kind='sync'));
create policy health_read on public.jobs4jsr_sync_health for select to authenticated using(exists(select 1 from public.jobs4jsr_members m where m.user_id=(select auth.uid()) and m.owner_id=jobs4jsr_sync_health.owner_id));
create policy health_publish on public.jobs4jsr_sync_health for insert to authenticated with check(exists(select 1 from public.jobs4jsr_members m where m.user_id=(select auth.uid()) and m.owner_id=jobs4jsr_sync_health.owner_id and m.kind='sync'));
create policy health_update on public.jobs4jsr_sync_health for update to authenticated using(exists(select 1 from public.jobs4jsr_members m where m.user_id=(select auth.uid()) and m.owner_id=jobs4jsr_sync_health.owner_id and m.kind='sync')) with check(exists(select 1 from public.jobs4jsr_members m where m.user_id=(select auth.uid()) and m.owner_id=jobs4jsr_sync_health.owner_id and m.kind='sync'));
