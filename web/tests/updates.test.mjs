import test from 'node:test';
import assert from 'node:assert/strict';
import {PGlite} from '@electric-sql/pglite';
import {readFile,readdir} from 'node:fs/promises';
import {updatePresentation,createUpdateController} from '../public/updates.js';
import {handle} from '../worker.mjs';
const owner='11111111-1111-1111-1111-111111111111',sync='22222222-2222-2222-2222-222222222222',stranger='33333333-3333-3333-3333-333333333333';
test('queue permissions, coalescing, leases, stale publication fencing, atomic publication and response-loss replay',async()=>{
 const db=new PGlite();
 try{
 await db.exec(`create role anon;create role authenticated;create schema auth;create table auth.users(id uuid primary key);create function auth.uid() returns uuid language sql stable as $$select nullif(current_setting('request.jwt.claim.sub',true),'')::uuid$$;grant usage on schema auth to authenticated;grant execute on function auth.uid() to authenticated;`);
 for(const file of (await readdir('supabase/migrations')).filter(f=>f.endsWith('.sql')).sort())await db.exec(await readFile('supabase/migrations/'+file,'utf8'));
 await db.exec(`insert into auth.users values('${owner}'),('${sync}'),('${stranger}');insert into jobs4jsr_members values('${owner}','${owner}','reader'),('${sync}','${owner}','sync');set role authenticated;select set_config('request.jwt.claim.sub','${owner}',false)`);
 const key='aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa';
 const requests=await Promise.all(Array.from({length:8},()=>db.query(`select jobs4jsr_request_update('${key}') as r`)));
 const request=requests[0].rows[0].r;
 assert.equal(new Set(requests.map(x=>x.rows[0].r.id)).size,1);
 assert.equal((await db.query("select jobs4jsr_request_update('bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb') as r")).rows[0].r.id,request.id);
 assert.equal('claim_token' in request,false);
 assert.equal((await db.query('select jobs4jsr_update_status() as s')).rows[0].s.runner,null);
 await assert.rejects(db.exec("update jobs4jsr_update_requests set state='completed'"));
 await assert.rejects(db.query('select claim_token from jobs4jsr_update_requests'));
 await assert.rejects(db.query('select jobs4jsr_claim_update()'));
 await db.exec(`select set_config('request.jwt.claim.sub','${stranger}',false)`);
 assert.equal((await db.query('select id from jobs4jsr_update_requests')).rows.length,0);
 await assert.rejects(db.query(`select jobs4jsr_request_update('${key}')`));
 await db.exec(`select set_config('request.jwt.claim.sub','${sync}',false)`);
 await assert.rejects(db.query(`select jobs4jsr_request_update('${key}')`));
 await db.query('select jobs4jsr_runner_heartbeat(null,null,false)');
 const first=(await db.query('select jobs4jsr_claim_update() as r')).rows[0].r;
 assert.equal((await db.query('select jobs4jsr_claim_update() as r')).rows[0].r,null);
 await db.exec(`reset role;update jobs4jsr_update_requests set lease_until=now()-interval '1 second';set role authenticated;select set_config('request.jwt.claim.sub','${sync}',false)`);
 await assert.rejects(db.query(`select jobs4jsr_runner_heartbeat('${first.id}','${first.claim_token}',true)`));
 let second=(await db.query('select jobs4jsr_claim_update() as r')).rows[0].r;
 assert.notEqual(first.claim_token,second.claim_token);
 await db.query('select jobs4jsr_fail_update($1,$2,$3)',[second.id,second.claim_token,'publication_failed']);
 assert.equal((await db.query('select jobs4jsr_claim_update() as r')).rows[0].r,null);
 const previousToken=second.claim_token;
 await db.exec(`reset role;update jobs4jsr_update_requests set available_at=now()-interval '1 second';set role authenticated;select set_config('request.jwt.claim.sub','${sync}',false)`);
 second=(await db.query('select jobs4jsr_claim_update() as r')).rows[0].r;
 assert.equal(second.attempt,3);
 await assert.rejects(db.query('select jobs4jsr_runner_heartbeat($1,$2,true)',[second.id,previousToken]));
 const payload={jobs:[{id:key,vacancy:{title:'Fixture'}}],runs:[],checks:[],summary:{new_jobs:1,refreshed_jobs:0,source_failures:[]}};
 await assert.rejects(db.query('select jobs4jsr_publish_update($1,$2,$3)',[first.id,first.claim_token,payload]));
 const broken={...payload,checks:[{run_id:'missing',source:'invalid',payload:{}}]};
 await assert.rejects(db.query('select jobs4jsr_publish_update($1,$2,$3)',[second.id,second.claim_token,broken]));
 assert.equal((await db.query('select * from jobs4jsr_jobs')).rows.length,0);
 const done=(await db.query('select jobs4jsr_publish_update($1,$2,$3) as r',[second.id,second.claim_token,payload])).rows[0].r;
 assert.equal(done.state,'completed');assert.equal(done.summary.new_jobs,1);
 const replay=(await db.query('select jobs4jsr_publish_update($1,$2,$3) as r',[second.id,second.claim_token,{...payload,jobs:[]}])).rows[0].r;
 assert.deepEqual(replay,done);
 assert.equal((await db.query('select * from jobs4jsr_jobs')).rows.length,1);
 await db.exec(`reset role;update jobs4jsr_update_requests set created_at=now()-interval '2 minutes';set role authenticated;select set_config('request.jwt.claim.sub','${owner}',false)`);
 const next=(await db.query(`select jobs4jsr_request_update('bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb') as r`)).rows[0].r;
 await db.exec(`reset role;update jobs4jsr_update_requests set expires_at=now()-interval '1 second' where id='${next.id}';set role authenticated;select set_config('request.jwt.claim.sub','${owner}',false)`);
 assert.equal((await db.query('select jobs4jsr_update_status() as s')).rows[0].s.request.error_code,'request_expired');
 await db.exec(`reset role;update jobs4jsr_update_requests set state='queued',expires_at=now()+interval '1 day',available_at=now(),attempt=3 where id='${next.id}';set role authenticated;select set_config('request.jwt.claim.sub','${sync}',false)`);
 assert.equal((await db.query('select jobs4jsr_claim_update() as r')).rows[0].r,null);
 await db.exec('reset role');
 assert.equal((await db.query('select error_code from jobs4jsr_update_requests where id=$1',[next.id])).rows[0].error_code,'attempts_exhausted');
 const jobsBefore=(await db.query('select * from jobs4jsr_jobs')).rows;
 await db.exec(await readFile('supabase/optional/jobs4jsr_manual_updates_rollback.sql','utf8'));
 assert.deepEqual((await db.query('select * from jobs4jsr_jobs')).rows,jobsBefore);
 assert.equal((await db.query("select to_regclass('public.jobs4jsr_update_requests') as r")).rows[0].r,null);
 await db.exec(await readFile('supabase/migrations/20261020043915_jobs4jsr_manual_updates.sql','utf8'));
 await db.exec('set role anon');
 await assert.rejects(db.query('select jobs4jsr_update_status()'));
 }finally{await db.close()}
});
test('visible offline/running/completed/warning/failed update states',()=>{
 assert.equal(updatePresentation({request:null}).label,'Run Update');
 assert.match(updatePresentation({request:{state:'queued'}}).message,/offline/);
 assert.equal(updatePresentation({request:{state:'running'},runner:{online:true}}).label,'Running update');
 assert.match(updatePresentation({request:{state:'completed',summary:{new_jobs:2,refreshed_jobs:8,source_failures:['Employer A']}}}).message,/2 new jobs.*8 existing jobs refreshed.*Employer A/);
 assert.match(updatePresentation({request:{state:'failed',error_code:'request_expired'}}).message,/did not collect/);
});
test('Worker requires Jess, same origin, explicit feature enablement and a valid idempotency key',async()=>{
 const old=global.fetch;const calls=[];
 const env={SUPABASE_URL:'https://example.supabase.co',SUPABASE_PUBLISHABLE_KEY:'test',JESS_USER_ID:owner,MANUAL_UPDATES_ENABLED:'true'};
 const req=(path,method='GET',body,origin='https://board.test')=>new Request('https://board.test/api/'+path,{method,headers:{Origin:origin,Cookie:'access=valid'},body:body?JSON.stringify(body):undefined});
 global.fetch=async(url,options)=>{calls.push({url,options});return Response.json(url.includes('/auth/')?{id:owner}:url.includes('jobs4jsr_members')?[{user_id:owner,owner_id:owner,kind:'reader'}]:{state:'queued',id:'request'})};
 try{
 assert.equal((await handle(req('update-requests','POST',{key:'bad'}),env)).status,400);
 assert.equal((await handle(req('update-requests','POST',{key:'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa'},'https://evil.test'),env)).status,403);
 assert.equal((await handle(req('update-status'),{...env,MANUAL_UPDATES_ENABLED:'false'})).status,503);
 assert.equal((await handle(req('update-requests','POST',{key:'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa'}),env)).status,202);
 assert.deepEqual(JSON.parse(calls.at(-1).options.body),{p_key:'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa'});
 global.fetch=async()=>Response.json({id:stranger});assert.equal((await handle(req('update-status'),env)).status,401);
 }finally{global.fetch=old}
});
test('controller ignores late status after sign-out and refreshes completion once',async()=>{
 const elements=Object.fromEntries(['run-update','update-status','health'].map(id=>[id,{disabled:true,textContent:''}]));
 let resolve;let refreshed=0;let callback;
 const controller=createUpdateController({document:{getElementById:id=>elements[id]},api:()=>new Promise(r=>resolve=r),onComplete:async()=>refreshed++,timers:{clearTimeout(){},setTimeout(fn){callback=fn}}});
 controller.start();controller.stop();resolve({request:{id:'x',state:'completed',summary:{}}});await new Promise(r=>setImmediate(r));
 assert.equal(refreshed,0);assert.equal(elements['run-update'].disabled,true);
 const status={request:{id:'x',state:'completed',summary:{new_jobs:0,refreshed_jobs:4,source_failures:[]}}};
 controller.start();resolve(status);await new Promise(r=>setImmediate(r));assert.equal(refreshed,1);
 const promise=callback();resolve(status);await promise;assert.equal(refreshed,1);controller.stop();
});

test('a lost enqueue response reuses its key; active request prevents repeat submissions',async()=>{
 const elements=Object.fromEntries(['run-update','update-status','health'].map(id=>[id,{disabled:true,textContent:''}]));
 let status={request:null,runner:{online:true}};const keys=[];
 const controller=createUpdateController({document:{getElementById:id=>elements[id]},api:async(path,options)=>{
  if(path==='/update-status')return status;
  keys.push(JSON.parse(options.body).key);
  if(keys.length===1)throw new Error('Network lost');
  status={request:{id:'queued',state:'queued'},runner:{online:false}};return status.request;
 },onComplete:async()=>{},timers:{setTimeout(){},clearTimeout(){}}});
 controller.start();await new Promise(r=>setImmediate(r));
 await elements['run-update'].onclick();await elements['run-update'].onclick();
 assert.equal(keys.length,2);assert.equal(keys[0],keys[1]);
 await elements['run-update'].onclick();assert.equal(keys.length,2);controller.stop();
});
