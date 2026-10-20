-- REVIEW ONLY: disable Worker flag and stop/quiesce poller first; archive queue.
-- This removes only the new control plane. Published jobs/decisions are retained.
begin;
drop function public.jobs4jsr_request_update(uuid),public.jobs4jsr_update_status(),public.jobs4jsr_claim_update(),public.jobs4jsr_runner_heartbeat(uuid,uuid,boolean),public.jobs4jsr_fail_update(uuid,uuid,text),public.jobs4jsr_publish_update(uuid,uuid,jsonb);
drop function jobs4jsr_control.publish(uuid,uuid,jsonb),jobs4jsr_control.fail(uuid,uuid,text),jobs4jsr_control.heartbeat(uuid,uuid,boolean),jobs4jsr_control.check_claim(uuid,uuid),jobs4jsr_control.claim(),jobs4jsr_control.enqueue(uuid),jobs4jsr_control.status(),jobs4jsr_control.actor(text);
drop schema jobs4jsr_control restrict;
drop table public.jobs4jsr_runner_status,public.jobs4jsr_update_requests;
commit;
