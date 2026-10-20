"""Catalogue reconciliation: vacancy state never overwrites application decisions."""
import hashlib,json,uuid
from . import database,deduplication,scoring,letters
FIELDS=('employer','title','location','description','job_type','posted','salary','hours','distance','match')

def digest(job):
 return hashlib.sha256(json.dumps({k:job.get(k) for k in FIELDS},sort_keys=True).encode()).hexdigest()

def reconcile(c,root,profile,found,notes,run_id,now,today):
 namespace=c.execute("SELECT value FROM metadata WHERE key='namespace'").fetchone()
 if not namespace:
  namespace=(str(uuid.uuid4()),);c.execute("INSERT INTO metadata VALUES('namespace',?)",namespace)
 previous=database.jobs(c);new=[];changed=[];duplicates=0;refreshed=set();prior_ids={j['id'] for j in previous}
 checks={x.source:x for x in getattr(notes,'checks',[])}
 def save(j):
  c.execute('UPDATE jobs SET payload=? WHERE id=?',(json.dumps({k:v for k,v in j.items() if k not in ('id','status')}),j['id']))
 def event(j,kind):
  c.execute('INSERT INTO vacancy_events(job_id,run_id,kind,changed,payload) VALUES(?,?,?,?,?)',(j['id'],run_id,kind,now,json.dumps({'vacancy_state':j.get('vacancy_state'),'fingerprint':digest(j)})))
 for j in previous:
  j.setdefault('legacy_application_status',j['status'])
  j.setdefault('stable_id',str(uuid.uuid5(uuid.UUID(namespace[0]),str(j['id']))));j['is_new']=j.get('run_id')==run_id;j['recommended']=False;save(j)
 for incoming in found:
  check=checks.get(incoming['source']);match=scoring.score(incoming,profile)
  old=next((j for j in previous+new if deduplication.duplicate(incoming,j)),None)
  if not match:
   if check:check.excluded+=1
   if old:
    refreshed.add(old['id'])
    old['vacancy_state']='no_longer_qualifies';old['last_verified']=now;save(old)
   continue
  incoming['match'],incoming['why']=match
  if check:check.qualified+=1
  if old:
   if old['id'] in prior_ids:refreshed.add(old['id'])
   duplicates+=1
   if check:check.duplicates+=1
   before=digest(old);prior_state=old.get('vacancy_state')
   alternate=old.setdefault('alternate_sources',[])
   alternate[:]=[x for x in alternate if (x['source'],x['url'])!=(incoming['source'],incoming['url'])]
   alternate.append({'source':incoming['source'],'url':incoming['url'],'verified_at':now})
   if incoming['url']==old['url']:
    protected={k:old.get(k) for k in ('id','status','found','run_id','stable_id','letter_md','letter_docx')}
    old.update(incoming);old.update(protected)
   old.pop('verification_warning',None)
   old.update(last_verified=now,vacancy_state='open',last_seen_run=run_id)
   if before!=digest(old) or prior_state=='closed':
    old['changed_at']=now;changed.append(old);event(old,'changed')
   save(old)
   continue
  incoming.update(found=today,last_verified=now,run_id=run_id,last_seen_run=run_id,vacancy_state='open',is_new=True,recommended=False,stable_id=str(uuid.uuid4()))
  incoming['letter_md'],incoming['letter_docx']=None,None
  incoming['id']=database.add(c,incoming);incoming['status']='New';new.append(incoming);event(incoming,'new')
  if check:check.selected+=1
 for check in checks.values():
  for url,state in check.observations.items():
   for old in previous:
    if old['url']==url and state=='closed' and old.get('last_seen_run')!=run_id:
     refreshed.add(old['id'])
     if old.get('vacancy_state')!='closed':old.update(vacancy_state='closed',changed_at=now,last_verified=now);event(old,'closed');changed.append(old)
     save(old)
  # A failed check creates uncertainty, not a closed advertisement.
  for old in previous:
   if old['source']==check.source and old.get('last_seen_run')!=run_id and old.get('vacancy_state') not in ('closed','no_longer_qualifies'):
    old['verification_warning']='Availability not confirmed by current source check'
    old['vacancy_state']='verification_unknown'
    save(old)
 for j in sorted([x for x in database.jobs(c) if (run_id.startswith('baseline-') or x.get('run_id')==run_id) and x.get('vacancy_state')=='open'],key=lambda x:(x['match'],x.get('posted') or ''),reverse=True)[:3]:
  j['recommended']=True
  if not j.get('letter_docx'):
   j['letter_md'],j['letter_docx']=letters.generate(j,profile,root,today)
  save(j)
 return dict(refreshed=len(refreshed),new=len(new),duplicates=duplicates,changed=len(changed),catalogue=[j for j in database.jobs(c) if j.get('vacancy_state','open')!='no_longer_qualifies'])
