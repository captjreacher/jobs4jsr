import argparse,json,sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo
from . import candidate,database,discovery,scoring,deduplication,letters,reporting,scheduler

def main():
    parser=argparse.ArgumentParser(); parser.add_argument('--root',type=Path,default=Path(__file__).resolve().parents[2])
    sub=parser.add_subparsers(dest='command',required=True)
    sub.add_parser('setup'); p=sub.add_parser('profile'); p.add_argument('--source',default='C:/DEV_LOCAL/TEMP')
    sub.add_parser('letters'); sub.add_parser('initial'); sub.add_parser('scheduled'); p=sub.add_parser('report'); p.add_argument('--run'); sub.add_parser('list')
    p=sub.add_parser('status'); p.add_argument('id',type=int); p.add_argument('status',choices=database.STATUSES)
    a=parser.parse_args(); root=a.root.resolve(); config=root/'config/settings.json'
    if not config.exists(): config.write_text((root/'config/settings.example.json').read_text(),encoding='utf-8')
    c=database.connect(root/'data/private/jobs.sqlite3')
    try:
        settings=json.loads(config.read_text())
        if a.command=='setup': print('Database and local configuration ready'); return
        if a.command=='profile': candidate.build(a.source,root/'data/private'); print('Local candidate profile created'); return
        if a.command=='status': database.status(c,a.id,a.status); print('Status updated; regenerate reports with report'); return
        if a.command=='list':
            for j in database.jobs(c): print(j['id'],j['status'],j['employer'],j['title'])
            return
        now=datetime.now(ZoneInfo('Pacific/Auckland')); today=now.date().isoformat()
        if a.command=='report':
            rows=database.jobs(c)
            if a.run: rows=[j for j in rows if j.get('run_id')==a.run]
            notes=['Historical view; last_verified stored in database. Verify advertisements again before applying.']
            print(reporting.report(root,today,rows,notes,a.run or 'history')); return
        profile=json.loads((root/'data/private/jess_profile.json').read_text())
        if a.command=='letters':
            for j in database.jobs(c):
                letters.generate(j,profile,root,j['found'])
            print('Letters regenerated from verified local profile'); return
        run_id=scheduler.due_slot(now) if a.command=='scheduled' else 'initial'
        # BEGIN IMMEDIATE serialises concurrent scheduled/manual launches.
        c.execute('BEGIN IMMEDIATE')
        prior=c.execute('SELECT completed FROM runs WHERE id=?',(run_id,)).fetchone()
        initial_existing=[j for j in database.jobs(c) if j.get('run_id')=='initial']
        if prior and prior[0] and (a.command!='initial' or len(initial_existing)>=5):
            c.rollback(); print('Run already completed:',run_id); return
        c.execute('INSERT INTO runs(id,started) VALUES(?,?) ON CONFLICT(id) DO UPDATE SET started=excluded.started,completed=NULL',(run_id,now.isoformat()))
        found,notes=discovery.discover(settings,today); previous=database.jobs(c); qualified=[]
        for j in found:
            if any(deduplication.duplicate(j,x) for x in previous):
                old=next(x for x in previous if deduplication.duplicate(j,x)); old['last_verified']=now.isoformat()
                old.update(recent=j['recent'],job_type=j['job_type'],description=j['description'],structured_job_type=j.get('structured_job_type'),uncertainties=j['uncertainties'])
                rescored=scoring.score(old,profile)
                if rescored: old['match'],old['why']=rescored
                c.execute('UPDATE jobs SET payload=? WHERE id=?',(json.dumps({k:v for k,v in old.items() if k not in ('id','status')}),old['id'])); continue
            match=scoring.score(j,profile)
            if match:
                j['match'],j['why']=match; qualified.append(j)
            else: notes.append('Excluded for role, requirements or radius: '+j['employer']+' '+j['title'])
        # Secondary ordering newest first within score.
        qualified=sorted(qualified,key=lambda j:(j['match'],j.get('posted') or ''),reverse=True)[:max(0,5-len(initial_existing)) if a.command=='initial' else 3]
        for j in qualified:
            j.update(found=today,last_verified=now.isoformat(),run_id=run_id)
            j['letter_md'],j['letter_docx']=letters.generate(j,profile,root,today)
            j['id']=database.add(c,j); j['status']='New'
        notes.append(f'Quota: {5 if a.command=="initial" else 3}; selected {len(qualified)} new vacancies. No vacancies invented. Status is tracked locally; no applications submitted.')
        report_rows=[j for j in database.jobs(c) if j.get('run_id')=='initial'] if a.command=='initial' else qualified
        output=reporting.report(root,today,report_rows,notes,run_id)
        c.execute('UPDATE runs SET completed=?,diagnostics=? WHERE id=?',(None if any(x.startswith('SOURCE FAILED') for x in notes) else datetime.now(ZoneInfo('Pacific/Auckland')).isoformat(),json.dumps(notes),run_id)); c.commit()
        print(output); print('New jobs:',len(qualified))
        if any(x.startswith('SOURCE FAILED') for x in notes): print('Source failure; inspect report',file=sys.stderr); sys.exit(2)
    finally:
        c.close()

if __name__=='__main__': main()
