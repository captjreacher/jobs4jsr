-- Hosted-letter enhancement only. NOT part of the two base migrations.
-- Requires separately approved Storage-owner execution and letter privacy approval.
-- Never transfer table ownership or elevate app/publisher roles to execute this.
do $$
begin
 if not exists (select 1 from pg_class where oid='storage.objects'::regclass and relrowsecurity) then
  raise exception 'Storage RLS must be enabled';
 end if;
 if not exists (select 1 from pg_class where oid='storage.objects'::regclass and pg_has_role(current_user,relowner,'USAGE')) then
  raise exception 'Approved Storage policy owner context required';
 end if;
end $$;
insert into storage.buckets(id,name,public,file_size_limit,allowed_mime_types) values('jobs4jsr-letters','jobs4jsr-letters',false,5242880,array['application/vnd.openxmlformats-officedocument.wordprocessingml.document','text/markdown']);
create policy jobs4jsr_letters_read on storage.objects for select to authenticated using(bucket_id='jobs4jsr-letters' and exists(select 1 from public.jobs4jsr_members m where m.user_id=(select auth.uid()) and m.owner_id::text=(storage.foldername(name))[1]));
create policy jobs4jsr_letters_insert on storage.objects for insert to authenticated with check(bucket_id='jobs4jsr-letters' and exists(select 1 from public.jobs4jsr_members m where m.user_id=(select auth.uid()) and m.owner_id::text=(storage.foldername(name))[1] and m.kind='sync'));
create policy jobs4jsr_letters_update on storage.objects for update to authenticated using(bucket_id='jobs4jsr-letters' and exists(select 1 from public.jobs4jsr_members m where m.user_id=(select auth.uid()) and m.owner_id::text=(storage.foldername(name))[1] and m.kind='sync')) with check(bucket_id='jobs4jsr-letters' and exists(select 1 from public.jobs4jsr_members m where m.user_id=(select auth.uid()) and m.owner_id::text=(storage.foldername(name))[1] and m.kind='sync'));
