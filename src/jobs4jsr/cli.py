"""Local command-line entry point. Manual searches never consume scheduler slots."""
import argparse
import json
import re
import sys
from datetime import datetime
from pathlib import Path
from uuid import uuid4
from zoneinfo import ZoneInfo
from . import candidate, database, discovery, scoring, deduplication, letters, reporting, scheduler, catalogue, sync, coordinator


def parser_for():
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[2])
    sub = parser.add_subparsers(dest='command', required=True)
    sub.add_parser('setup')
    p = sub.add_parser('profile'); p.add_argument('--source', default='C:/DEV_LOCAL/TEMP')
    sub.add_parser('baseline'); sub.add_parser('sync')
    p=sub.add_parser('letters');p.add_argument('--job-id',type=int,required=True)
    sub.add_parser('initial'); p=sub.add_parser('scheduled');p.add_argument('--slot',help=argparse.SUPPRESS)
    p = sub.add_parser('search'); p.add_argument('--run-id', help='Optional manual identifier, safely repeatable')
    p = sub.add_parser('report'); p.add_argument('--run')
    sub.add_parser('list')
    sub.add_parser('sources')
    p = sub.add_parser('status'); p.add_argument('id', type=int); p.add_argument('status', choices=database.STATUSES)
    return parser


def main(argv=None, update_control=None):
    a = parser_for().parse_args(argv)
    root = a.root.resolve()
    if a.command in ('initial','baseline','scheduled','search','sync','letters'):
        slot = (a.slot or scheduler.due_slot(datetime.now(ZoneInfo('Pacific/Auckland')))) if a.command == 'scheduled' else None
        if slot and not re.fullmatch(r'\d{4}-\d{2}-\d{2}-scheduled',slot):raise ValueError('Invalid scheduled slot')
        with coordinator.command(root, a.command, slot) as acquired:
            if acquired:
                return execute(a, update_control)
        return
    return execute(a, update_control)


def execute(a, update_control=None):
    root = a.root.resolve(); config = root / 'config/settings.json'
    sync.load_env(root)
    if not config.exists():
        config.write_text((root / 'config/settings.example.json').read_text(encoding='utf-8'), encoding='utf-8')
    c = database.connect(root / 'data/private/jobs.sqlite3')
    try:
        settings = json.loads(config.read_text(encoding='utf-8'))
        if a.command == 'setup': print('Database and local configuration ready'); return
        if a.command == 'profile':
            candidate.build(a.source, root / 'data/private'); print('Local candidate profile created'); return
        if a.command == 'status':
            database.status(c, a.id, a.status); print('Status updated; regenerate reports with report'); return
        if a.command == 'list':
            for j in database.jobs(c): print(j['id'], j['status'], j['employer'], j['title'])
            return
        if a.command == 'sync':
            sync.publish(c,root); return
        if a.command == 'sources':
            print(json.dumps(database.source_checks(c), indent=2, ensure_ascii=True)); return
        now = datetime.now(ZoneInfo('Pacific/Auckland')); today = now.date().isoformat()
        if a.command == 'report':
            rows = database.jobs(c)
            if a.run: rows = [j for j in rows if j.get('run_id') == a.run]
            checks = database.source_checks(c, a.run) if a.run else []
            print(reporting.report(root, today, rows,
                  ['Historical view; verify advertisements again before applying.'],
                  a.run or 'history', source_checks=checks)); return
        profile = json.loads((root / 'data/private/jess_profile.json').read_text(encoding='utf-8'))
        if a.command == 'letters':
            j=next((j for j in database.jobs(c) if j['id']==a.job_id),None)
            if not j:raise ValueError('Unknown job ID')
            j['letter_md'],j['letter_docx']=letters.generate(j,profile,root,today)
            c.execute('UPDATE jobs SET payload=? WHERE id=?',(json.dumps({k:v for k,v in j.items() if k not in ('id','status')}),j['id']));c.commit()
            print('Letter generated locally; upload requires separate approval'); return
        if a.command == 'scheduled':
            run_id = a.slot or scheduler.due_slot(now)
        elif a.command == 'initial':
            run_id = 'initial'
        elif a.command == 'baseline':
            run_id='baseline-'+now.strftime('%Y-%m-%d-%H%M%S')+'-'+uuid4().hex[:8]
        else:
            suffix = a.run_id or now.strftime('%Y-%m-%d-%H%M%S') + '-' + uuid4().hex[:8]
            if not re.fullmatch(r'[A-Za-z0-9_-]{1,100}', suffix):
                raise ValueError('Manual run ID must contain only letters, digits, underscore and hyphen')
            run_id = 'manual-' + suffix
        checkpoint = c.execute('SELECT summary,published FROM update_checkpoints WHERE run_id=?',(run_id,)).fetchone()
        if checkpoint and sync.configured() and (not checkpoint[1] or update_control is not None):
            sync.publish(c,root,update_control=update_control,summary=json.loads(checkpoint[0]))
            c.execute('UPDATE update_checkpoints SET published=1 WHERE run_id=?',(run_id,));c.commit()
            print('Recovered publication without rediscovery:',run_id)
            if update_control is None and json.loads(checkpoint[0]).get('source_failures'):
                # Scheduled source retries retain their pre-existing exit-2 contract.
                sys.exit(2)
            return
        c.execute('BEGIN IMMEDIATE')
        prior = c.execute('SELECT completed FROM runs WHERE id=?', (run_id,)).fetchone()
        existing = [j for j in database.jobs(c) if j.get('run_id') == run_id]
        if prior and prior[0]:
            c.rollback(); print('Run already completed:', run_id); return
        c.execute('''INSERT INTO runs(id,started) VALUES(?,?)
            ON CONFLICT(id) DO UPDATE SET started=excluded.started,completed=NULL''', (run_id, now.isoformat()))
        previous=database.jobs(c)
        found, notes = discovery.discover(settings, today, previous)
        result=catalogue.reconcile(c,root,profile,found,notes,run_id,now.isoformat(),today)
        checks={check.source:check for check in getattr(notes,'checks',[])}
        selected=[j for j in result['catalogue'] if j.get('run_id')==run_id]
        check_rows = discovery.serialise_checks(notes)
        database.save_source_checks(c, run_id, check_rows)
        for row in check_rows:
            checks[row['source']].last_successful_check = row['last_successful_check']
        if hasattr(notes, 'refresh'): notes.refresh()
        notes.append(f"Uncapped catalogue: {result['new']} new, {result['duplicates']} duplicates, {result['changed']} changed. Top three NEW jobs are recommendations; all qualifying jobs are retained.")
        report_rows = result['catalogue']
        output = reporting.report(root, today, report_rows, notes, run_id, source_checks=check_rows)
        failed = any(check.errors for check in checks.values()) or any(x.startswith('SOURCE FAILED') for x in notes)
        c.execute('UPDATE runs SET completed=?,diagnostics=? WHERE id=?',
                  (None if failed else datetime.now(ZoneInfo('Pacific/Auckland')).isoformat(), json.dumps(list(notes)), run_id))
        summary = {'new_jobs':result['new'],'refreshed_jobs':result['refreshed'],
                   'source_failures':[row['source'] for row in check_rows if row.get('errors') or row.get('status')!='success'],
                   'all_sources_failed':bool(check_rows) and all(row.get('status')=='failed' for row in check_rows)}
        c.execute('INSERT OR REPLACE INTO update_checkpoints(run_id,summary,published) VALUES(?,?,0)',(run_id,json.dumps(summary)))
        c.commit()
        print(output); print('Run:', run_id); print('New jobs:', len(selected))
        if sync.configured():
            sync.publish(c,root,update_control=update_control,summary=summary)
            c.execute('UPDATE update_checkpoints SET published=1 WHERE run_id=?',(run_id,));c.commit()
        if failed:
            print('One or more sources failed; remaining sources completed. Inspect report.', file=sys.stderr)
            sys.exit(2)
    finally:
        c.close()

if __name__ == '__main__': main()
