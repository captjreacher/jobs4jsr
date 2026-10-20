-- LOCAL REVIEW CANDIDATE. Apply only under separate production authorisation.
create schema jobs4jsr_control;
revoke all on schema jobs4jsr_control from public;
grant usage on schema jobs4jsr_control to authenticated;
create table public.jobs4jsr_update_requests (
 id uuid primary key default gen_random_uuid(), owner_id uuid not null references auth.users(id),
 request_key uuid not null, state text not null default 'queued' check(state in ('queued','running','completed','failed')),
 created_at timestamptz not null default now(), expires_at timestamptz not null default now()+interval '24 hours',
 available_at timestamptz not null default now(), started_at timestamptz, finished_at timestamptz,
 attempt integer not null default 0 check(attempt between 0 and 3), claim_token uuid,
 lease_until timestamptz, summary jsonb, error_code text, unique(owner_id,request_key)
);
create unique index jobs4jsr_one_active_update on public.jobs4jsr_update_requests(owner_id) where state in ('queued','running');
create table public.jobs4jsr_runner_status (
 owner_id uuid primary key references auth.users(id), runner_user_id uuid not null references auth.users(id),
 heartbeat_at timestamptz not null, busy boolean not null default false
);
alter table public.jobs4jsr_update_requests enable row level security;
alter table public.jobs4jsr_runner_status enable row level security;
revoke all on public.jobs4jsr_update_requests,public.jobs4jsr_runner_status from public,anon,authenticated;
-- No direct writes and no SELECT privilege for claim_token. All transitions use restricted RPCs.
grant select(id,owner_id,request_key,state,created_at,expires_at,available_at,started_at,finished_at,attempt,lease_until,summary,error_code) on public.jobs4jsr_update_requests to authenticated;
grant select(owner_id,heartbeat_at,busy) on public.jobs4jsr_runner_status to authenticated;
create policy updates_read on public.jobs4jsr_update_requests for select to authenticated using(exists(select 1 from public.jobs4jsr_members m where m.user_id=(select auth.uid()) and m.owner_id=jobs4jsr_update_requests.owner_id));
create policy runner_read on public.jobs4jsr_runner_status for select to authenticated using(exists(select 1 from public.jobs4jsr_members m where m.user_id=(select auth.uid()) and m.owner_id=jobs4jsr_runner_status.owner_id));

create function jobs4jsr_control.actor(p_kind text) returns uuid language plpgsql security definer set search_path='' as $$
declare v_owner uuid; begin
 select owner_id into v_owner from public.jobs4jsr_members where user_id=auth.uid() and kind=p_kind;
 if v_owner is null then raise exception 'Not authorised' using errcode='42501'; end if;
 return v_owner; end $$;
create function jobs4jsr_control.status() returns jsonb language plpgsql security definer set search_path='' as $$
declare v_owner uuid; v_request jsonb; v_runner jsonb; begin
 v_owner:=jobs4jsr_control.actor('reader');
 update public.jobs4jsr_update_requests set state='failed',error_code='request_expired',finished_at=now() where owner_id=v_owner and state='queued' and expires_at<=now();
 select to_jsonb(r)-'claim_token' into v_request from public.jobs4jsr_update_requests r where owner_id=v_owner order by created_at desc,id desc limit 1;
 select jsonb_build_object('heartbeat_at',heartbeat_at,'busy',busy,'online',heartbeat_at>now()-interval '2 minutes') into v_runner from public.jobs4jsr_runner_status where owner_id=v_owner;
 return jsonb_build_object('request',v_request,'runner',v_runner,'server_now',now(),
  'last_successful_update',(select last_successful_sync from public.jobs4jsr_sync_health where owner_id=v_owner));
end $$;
create function jobs4jsr_control.enqueue(p_key uuid) returns jsonb language plpgsql security definer set search_path='' as $$
declare v_owner uuid; r public.jobs4jsr_update_requests; begin
 v_owner:=jobs4jsr_control.actor('reader');
 if p_key is null then raise exception 'Request key required'; end if;
 perform pg_advisory_xact_lock(hashtextextended(v_owner::text,0));
 select * into r from public.jobs4jsr_update_requests where owner_id=v_owner and request_key=p_key;
 if found then return to_jsonb(r)-'claim_token'; end if;
 update public.jobs4jsr_update_requests set state='failed',error_code='request_expired',finished_at=now() where owner_id=v_owner and state='queued' and expires_at<=now();
 select * into r from public.jobs4jsr_update_requests where owner_id=v_owner and state in ('queued','running');
 if found then return to_jsonb(r)-'claim_token'; end if;
 select * into r from public.jobs4jsr_update_requests where owner_id=v_owner and created_at>now()-interval '1 minute' order by created_at desc limit 1;
 if found then return to_jsonb(r)-'claim_token'; end if;
 insert into public.jobs4jsr_update_requests(owner_id,request_key) values(v_owner,p_key) returning * into r;
 return to_jsonb(r)-'claim_token';
end $$;
create function jobs4jsr_control.claim() returns jsonb language plpgsql security definer set search_path='' as $$
declare v_owner uuid; r public.jobs4jsr_update_requests; begin
 v_owner:=jobs4jsr_control.actor('sync');
 perform pg_advisory_xact_lock(hashtextextended(v_owner::text,0));
 if exists(select 1 from public.jobs4jsr_runner_status where owner_id=v_owner and runner_user_id<>auth.uid()) then raise exception 'Runner identity mismatch' using errcode='42501'; end if;
 update public.jobs4jsr_update_requests set state='failed',error_code='request_expired',finished_at=now() where owner_id=v_owner and state='queued' and expires_at<=now();
 select * into r from public.jobs4jsr_update_requests where owner_id=v_owner and
  ((state='queued' and available_at<=now()) or (state='running' and lease_until<=now())) for update;
 if not found then return null; end if;
 if r.attempt>=3 then
  update public.jobs4jsr_update_requests set state='failed',error_code='attempts_exhausted',finished_at=now(),claim_token=null where id=r.id;
  return null;
 end if;
 update public.jobs4jsr_update_requests set state='running',attempt=attempt+1,claim_token=gen_random_uuid(),lease_until=now()+interval '2 minutes',started_at=coalesce(started_at,now()),error_code=null where id=r.id returning * into r;
 return to_jsonb(r);
end $$;
create function jobs4jsr_control.check_claim(p_request uuid,p_token uuid) returns uuid language plpgsql security definer set search_path='' as $$
declare v_owner uuid; begin
 v_owner:=jobs4jsr_control.actor('sync');
 if exists(select 1 from public.jobs4jsr_runner_status where owner_id=v_owner and runner_user_id<>auth.uid()) then raise exception 'Runner identity mismatch' using errcode='42501'; end if;
 perform 1 from public.jobs4jsr_update_requests where id=p_request and owner_id=v_owner and state='running' and claim_token=p_token and lease_until>now() for update;
 if not found then raise exception 'Claim is no longer valid' using errcode='42501'; end if;
 return v_owner;
end $$;
create function jobs4jsr_control.heartbeat(p_request uuid,p_token uuid,p_busy boolean) returns boolean language plpgsql security definer set search_path='' as $$
declare v_owner uuid; begin
 v_owner:=jobs4jsr_control.actor('sync');
 insert into public.jobs4jsr_runner_status(owner_id,runner_user_id,heartbeat_at,busy) values(v_owner,auth.uid(),now(),p_busy)
 on conflict(owner_id) do update set heartbeat_at=excluded.heartbeat_at,busy=excluded.busy where jobs4jsr_runner_status.runner_user_id=auth.uid();
 if not found then raise exception 'Runner identity mismatch' using errcode='42501'; end if;
 if p_request is not null then
  perform jobs4jsr_control.check_claim(p_request,p_token);
  update public.jobs4jsr_update_requests set lease_until=now()+interval '2 minutes' where id=p_request;
 end if;
 return true;
end $$;
create function jobs4jsr_control.fail(p_request uuid,p_token uuid,p_code text) returns boolean language plpgsql security definer set search_path='' as $$
begin
 perform jobs4jsr_control.check_claim(p_request,p_token);
 if p_code not in ('discovery_failed','publication_failed','run_timeout') then raise exception 'Invalid error code'; end if;
 update public.jobs4jsr_update_requests set state=case when attempt>=3 then 'failed' else 'queued' end,
 error_code=p_code,available_at=now()+make_interval(secs=>attempt*60),finished_at=case when attempt>=3 then now() else null end,
 claim_token=null,lease_until=null where id=p_request;
 return true;
end $$;
create function jobs4jsr_control.publish(p_request uuid,p_token uuid,p_payload jsonb) returns jsonb language plpgsql security definer set search_path='' as $$
declare v_owner uuid; item jsonb; existing_owner uuid; r public.jobs4jsr_update_requests; v_summary jsonb; begin
 v_owner:=jobs4jsr_control.actor('sync');
 -- Lost response retry: same terminal claim is acknowledged without publishing again.
 select * into r from public.jobs4jsr_update_requests where id=p_request and owner_id=v_owner for update;
 if r.state in ('completed','failed') and r.claim_token=p_token and r.summary is not null then return to_jsonb(r)-'claim_token'; end if;
 perform jobs4jsr_control.check_claim(p_request,p_token);
 if jsonb_typeof(p_payload->'jobs')<>'array' or jsonb_array_length(p_payload->'jobs')>10000 then raise exception 'Invalid catalogue payload'; end if;
 for item in select value from jsonb_array_elements(p_payload->'jobs') loop
  select owner_id into existing_owner from public.jobs4jsr_jobs where id=(item->>'id')::uuid;
  if found and existing_owner<>v_owner then raise exception 'Job owner mismatch' using errcode='42501'; end if;
  insert into public.jobs4jsr_jobs(id,owner_id,vacancy) values((item->>'id')::uuid,v_owner,item->'vacancy')
   on conflict(id) do update set vacancy=excluded.vacancy where jobs4jsr_jobs.owner_id=v_owner;
  if not found then raise exception 'Job owner mismatch' using errcode='42501'; end if;
 end loop;
 for item in select value from jsonb_array_elements(p_payload->'runs') loop
  select owner_id into existing_owner from public.jobs4jsr_runs where id=item->>'id';
  if found and existing_owner<>v_owner then raise exception 'Run owner mismatch' using errcode='42501'; end if;
  insert into public.jobs4jsr_runs(id,owner_id,started,completed,diagnostics) values(item->>'id',v_owner,(item->>'started')::timestamptz,(item->>'completed')::timestamptz,item->'diagnostics')
   on conflict(id) do update set started=excluded.started,completed=excluded.completed,diagnostics=excluded.diagnostics where jobs4jsr_runs.owner_id=v_owner;
  if not found then raise exception 'Run owner mismatch' using errcode='42501'; end if;
 end loop;
 for item in select value from jsonb_array_elements(p_payload->'checks') loop
  if not exists(select 1 from public.jobs4jsr_runs where id=item->>'run_id' and owner_id=v_owner) then raise exception 'Check owner mismatch' using errcode='42501'; end if;
  insert into public.jobs4jsr_source_checks(run_id,source,owner_id,payload) values(item->>'run_id',item->>'source',v_owner,item->'payload')
   on conflict(run_id,source) do update set payload=excluded.payload where jobs4jsr_source_checks.owner_id=v_owner;
  if not found then raise exception 'Check owner mismatch' using errcode='42501'; end if;
 end loop;
 v_summary:=jsonb_build_object('new_jobs',greatest(0,(p_payload->'summary'->>'new_jobs')::integer),
 'refreshed_jobs',greatest(0,(p_payload->'summary'->>'refreshed_jobs')::integer),
 'source_failures',coalesce(p_payload->'summary'->'source_failures','[]'::jsonb),'published_at',now());
 insert into public.jobs4jsr_sync_health(owner_id,last_successful_sync) values(v_owner,now()) on conflict(owner_id) do update set last_successful_sync=excluded.last_successful_sync;
 update public.jobs4jsr_update_requests set state=case when coalesce((p_payload->'summary'->>'all_sources_failed')::boolean,false) then 'failed' else 'completed' end,
 summary=v_summary,finished_at=now(),lease_until=null,error_code=case when coalesce((p_payload->'summary'->>'all_sources_failed')::boolean,false) then 'discovery_failed' else null end where id=p_request returning * into r;
 return to_jsonb(r)-'claim_token';
end $$;

-- Exposed invoker wrappers; privileged bodies live in the non-exposed schema.
create function public.jobs4jsr_request_update(p_key uuid) returns jsonb language sql security invoker set search_path='' as $$select jobs4jsr_control.enqueue(p_key)$$;
create function public.jobs4jsr_update_status() returns jsonb language sql security invoker set search_path='' as $$select jobs4jsr_control.status()$$;
create function public.jobs4jsr_claim_update() returns jsonb language sql security invoker set search_path='' as $$select jobs4jsr_control.claim()$$;
create function public.jobs4jsr_runner_heartbeat(p_request uuid,p_token uuid,p_busy boolean) returns boolean language sql security invoker set search_path='' as $$select jobs4jsr_control.heartbeat(p_request,p_token,p_busy)$$;
create function public.jobs4jsr_fail_update(p_request uuid,p_token uuid,p_code text) returns boolean language sql security invoker set search_path='' as $$select jobs4jsr_control.fail(p_request,p_token,p_code)$$;
create function public.jobs4jsr_publish_update(p_request uuid,p_token uuid,p_payload jsonb) returns jsonb language sql security invoker set search_path='' as $$select jobs4jsr_control.publish(p_request,p_token,p_payload)$$;
revoke execute on all functions in schema jobs4jsr_control from public,anon,authenticated;
grant execute on all functions in schema jobs4jsr_control to authenticated;
revoke execute on function public.jobs4jsr_request_update(uuid),public.jobs4jsr_update_status(),public.jobs4jsr_claim_update(),public.jobs4jsr_runner_heartbeat(uuid,uuid,boolean),public.jobs4jsr_fail_update(uuid,uuid,text),public.jobs4jsr_publish_update(uuid,uuid,jsonb) from public,anon;
grant execute on function public.jobs4jsr_request_update(uuid),public.jobs4jsr_update_status(),public.jobs4jsr_claim_update(),public.jobs4jsr_runner_heartbeat(uuid,uuid,boolean),public.jobs4jsr_fail_update(uuid,uuid,text),public.jobs4jsr_publish_update(uuid,uuid,jsonb) to authenticated;
