-- Apply only after project/user approval. No existing ecosystem table is modified.
create table public.jobs4jsr_members (
 user_id uuid primary key references auth.users(id), owner_id uuid not null references auth.users(id),
 kind text not null check(kind in ('reader','sync')), check(kind='sync' or user_id=owner_id)
);
create table public.jobs4jsr_jobs (
 id uuid primary key,owner_id uuid not null references auth.users(id),vacancy jsonb not null,
 letters jsonb not null default '{}',unique(id,owner_id)
);
create table public.jobs4jsr_decisions (
 job_id uuid primary key,owner_id uuid not null,saved boolean not null default false,
 dismissed boolean not null default false,applied boolean not null default false,
 foreign key(job_id,owner_id) references public.jobs4jsr_jobs(id,owner_id)
);
alter table public.jobs4jsr_members enable row level security;
alter table public.jobs4jsr_jobs enable row level security;
alter table public.jobs4jsr_decisions enable row level security;
revoke all on public.jobs4jsr_members,public.jobs4jsr_jobs,public.jobs4jsr_decisions from public,anon,authenticated;
grant select on public.jobs4jsr_members to authenticated;
grant select,insert,update on public.jobs4jsr_jobs,public.jobs4jsr_decisions to authenticated;
create policy member_self on public.jobs4jsr_members for select to authenticated using(user_id=(select auth.uid()));
create policy jobs_read on public.jobs4jsr_jobs for select to authenticated using(exists(select 1 from public.jobs4jsr_members m where m.user_id=(select auth.uid()) and m.owner_id=jobs4jsr_jobs.owner_id));
create policy jobs_sync_insert on public.jobs4jsr_jobs for insert to authenticated with check(exists(select 1 from public.jobs4jsr_members m where m.user_id=(select auth.uid()) and m.owner_id=jobs4jsr_jobs.owner_id and m.kind='sync'));
create policy jobs_sync_update on public.jobs4jsr_jobs for update to authenticated using(exists(select 1 from public.jobs4jsr_members m where m.user_id=(select auth.uid()) and m.owner_id=jobs4jsr_jobs.owner_id and m.kind='sync')) with check(exists(select 1 from public.jobs4jsr_members m where m.user_id=(select auth.uid()) and m.owner_id=jobs4jsr_jobs.owner_id and m.kind='sync'));
create policy decisions_read on public.jobs4jsr_decisions for select to authenticated using(owner_id=(select auth.uid()) and exists(select 1 from public.jobs4jsr_members m where m.user_id=(select auth.uid()) and m.kind='reader'));
create policy decisions_insert on public.jobs4jsr_decisions for insert to authenticated with check(owner_id=(select auth.uid()) and exists(select 1 from public.jobs4jsr_members m where m.user_id=(select auth.uid()) and m.kind='reader'));
create policy decisions_update on public.jobs4jsr_decisions for update to authenticated using(owner_id=(select auth.uid()) and exists(select 1 from public.jobs4jsr_members m where m.user_id=(select auth.uid()) and m.kind='reader')) with check(owner_id=(select auth.uid()) and exists(select 1 from public.jobs4jsr_members m where m.user_id=(select auth.uid()) and m.kind='reader'));

-- No hosted-letter bucket or Storage policies are installed by the base release.
-- Optional owner-only setup is in supabase/optional/jobs4jsr_letters_owner_only.sql.
