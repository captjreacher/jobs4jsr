"""Idempotent publication using a dedicated, RLS-constrained Supabase Auth account."""
import os,json,hashlib
from datetime import datetime,timezone
from pathlib import Path
import requests
from . import database
PUBLIC_FIELDS=('employer','title','source','distance','location','job_type','match','why','found','posted','url','vacancy_state','verification_warning','is_new','recommended','changed_at','last_verified','salary','hours','legacy_application_status','alternate_sources','vacancy_id')

def configured():return bool(os.environ.get('JOBS4JSR_SUPABASE_URL'))

def load_env(root):
 """Load only Jobs4JSR settings from a private file; never execute its contents."""
 path=root/'.env'
 if not path.exists():return
 for line in path.read_text(encoding='utf-8-sig').splitlines():
  if not line.strip() or line.lstrip().startswith('#'):continue
  key,separator,value=line.partition('=')
  if separator and key.strip().startswith('JOBS4JSR_'):
   os.environ.setdefault(key.strip(),value.strip().strip('\"\''))

def projection(job,owner):
 return {'id':job['stable_id'],'owner_id':owner,'vacancy':{k:job.get(k) for k in PUBLIC_FIELDS}}

def publish(c,root,session=None):
 env=os.environ
 required=('JOBS4JSR_SUPABASE_URL','JOBS4JSR_PUBLISHABLE_KEY','JOBS4JSR_SYNC_EMAIL','JOBS4JSR_SYNC_PASSWORD','JOBS4JSR_OWNER_ID')
 if not all(env.get(k) for k in required):raise ValueError('Sync is not configured: see docs/hosted-board.md. No credentials inferred.')
 base=env[required[0]].rstrip('/')
 if not base.startswith('https://'):raise ValueError('Sync requires HTTPS')
 session=session or requests.Session();session.headers.update(apikey=env[required[1]])
 attempted=datetime.now(timezone.utc).isoformat()
 try:
  r=session.post(base+'/auth/v1/token?grant_type=password',json={'email':env[required[2]],'password':env[required[3]]},timeout=30);r.raise_for_status()
  token=r.json()['access_token'];session.headers['Authorization']='Bearer '+token
  for job in database.jobs(c):
   if not job.get('stable_id'):continue
   row=projection(job,env[required[4]])
   paths={}
   for kind in ('docx','md'):
    relative=job.get('letter_'+kind)
    if not relative or env.get('JOBS4JSR_LETTER_UPLOAD_APPROVED')!='true':continue
    path=(root/relative).resolve()
    if not path.is_relative_to((root/'outputs/letters').resolve()):raise ValueError('Letter path outside private letter directory')
    content=path.read_bytes();digest=hashlib.sha256(content).hexdigest()
    key=f"{row['owner_id']}/{row['id']}/{digest}.{kind}";paths[kind]=key
    r=session.post(base+'/storage/v1/object/jobs4jsr-letters/'+key,data=content,headers={'x-upsert':'true','Content-Type':'application/vnd.openxmlformats-officedocument.wordprocessingml.document' if kind=='docx' else 'text/markdown'},timeout=30);r.raise_for_status()
   if env.get('JOBS4JSR_LETTER_UPLOAD_APPROVED')=='true':row['letters']=paths
   # Decisions are deliberately absent from this upsert.
   r=session.post(base+'/rest/v1/jobs4jsr_jobs?on_conflict=id',json=row,headers={'Prefer':'resolution=merge-duplicates'},timeout=30);r.raise_for_status()
  runs=[dict(id=i,started=s,completed=f,diagnostics=json.loads(d or '[]')) for i,s,f,d in c.execute('SELECT id,started,completed,diagnostics FROM runs')]
  checks=[dict(run_id=i,source=s,payload=json.loads(p)) for i,s,p in c.execute('SELECT run_id,source,payload FROM source_checks')]
  for table,rows,conflict in [('jobs4jsr_runs',runs,'id'),('jobs4jsr_source_checks',checks,'run_id,source')]:
   for row in rows:
    row['owner_id']=env[required[4]]
    r=session.post(base+'/rest/v1/'+table+'?on_conflict='+conflict,json=row,headers={'Prefer':'resolution=merge-duplicates'},timeout=30);r.raise_for_status()
  r=session.post(base+'/rest/v1/jobs4jsr_sync_health?on_conflict=owner_id',json={'owner_id':env[required[4]],'last_successful_sync':attempted},headers={'Prefer':'resolution=merge-duplicates'},timeout=30);r.raise_for_status()
  c.execute('INSERT INTO sync_runs(attempted,status) VALUES(?,?)',(attempted,'success'));c.commit();print('Hosted catalogue synchronised')
 except Exception as exc:
  c.execute('INSERT INTO sync_runs(attempted,status,error) VALUES(?,?,?)',(attempted,'failed',type(exc).__name__));c.commit()
  raise RuntimeError('Sync failed; local results retained. Retry with the sync command. See local sync_runs for error type.') from None
