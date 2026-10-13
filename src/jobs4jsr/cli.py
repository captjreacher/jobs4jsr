"""Local command-line entry point. Manual searches never consume scheduler slots."""
import argparse
import json
import re
import sys
from datetime import datetime
from pathlib import Path
from uuid import uuid4
from zoneinfo import ZoneInfo
from . import candidate, database, discovery, scoring, deduplication, letters, reporting, scheduler


def parser_for():
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[2])
    sub = parser.add_subparsers(dest='command', required=True)
    sub.add_parser('setup')
    p = sub.add_parser('profile'); p.add_argument('--source', default='C:/DEV_LOCAL/TEMP')
    sub.add_parser('letters'); sub.add_parser('initial'); sub.add_parser('scheduled')
    p = sub.add_parser('search'); p.add_argument('--run-id', help='Optional manual identifier, safely repeatable')
    p = sub.add_parser('report'); p.add_argument('--run')
    sub.add_parser('list')
    sub.add_parser('sources')
    p = sub.add_parser('status'); p.add_argument('id', type=int); p.add_argument('status', choices=database.STATUSES)
    return parser


def main():
    a = parser_for().parse_args()
    root = a.root.resolve(); config = root / 'config/settings.json'
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
            for j in database.jobs(c): letters.generate(j, profile, root, j['found'])
            print('Letters regenerated from verified local profile'); return
        if a.command == 'scheduled':
            run_id = scheduler.due_slot(now)
        elif a.command == 'initial':
            run_id = 'initial'
        else:
            suffix = a.run_id or now.strftime('%Y-%m-%d-%H%M%S') + '-' + uuid4().hex[:8]
            if not re.fullmatch(r'[A-Za-z0-9_-]{1,100}', suffix):
                raise ValueError('Manual run ID must contain only letters, digits, underscore and hyphen')
            run_id = 'manual-' + suffix
        quota = 5 if a.command == 'initial' else 3
        c.execute('BEGIN IMMEDIATE')
        prior = c.execute('SELECT completed FROM runs WHERE id=?', (run_id,)).fetchone()
        existing = [j for j in database.jobs(c) if j.get('run_id') == run_id]
        if prior and prior[0] and (a.command != 'initial' or len(existing) >= quota):
            c.rollback(); print('Run already completed:', run_id); return
        c.execute('''INSERT INTO runs(id,started) VALUES(?,?)
            ON CONFLICT(id) DO UPDATE SET started=excluded.started,completed=NULL''', (run_id, now.isoformat()))
        found, notes = discovery.discover(settings, today)
        previous, qualified = database.jobs(c), []
        checks = {check.source: check for check in getattr(notes, 'checks', [])}
        for j in found:
            check = checks.get(j['source'])
            match = scoring.score(j, profile)
            if not match:
                if check: check.excluded += 1
                continue
            if check: check.qualified += 1
            duplicate = next((old for old in previous + qualified if deduplication.duplicate(j, old)), None)
            if duplicate:
                if check: check.duplicates += 1
                duplicate['last_verified'] = now.isoformat()
                alternate = duplicate.setdefault('alternate_sources', [])
                evidence = dict(source=j['source'], url=j['url'], verified_at=now.isoformat())
                alternate[:] = [x for x in alternate if (x['source'], x['url']) != (j['source'], j['url'])]
                alternate.append(evidence)
                if j['url'] == duplicate['url']:
                    duplicate.update(recent=j['recent'], job_type=j['job_type'], description=j['description'],
                                     structured_job_type=j.get('structured_job_type'), uncertainties=j['uncertainties'])
                    duplicate['match'], duplicate['why'] = match
                if duplicate in previous:
                    payload = {k: v for k, v in duplicate.items() if k not in ('id', 'status')}
                    c.execute('UPDATE jobs SET payload=? WHERE id=?', (json.dumps(payload), duplicate['id']))
                continue
            j['match'], j['why'] = match
            qualified.append(j)
        # Retry budget includes jobs already committed to this slot, not three more per attempt.
        selected = sorted(qualified, key=lambda j: (j['match'], j.get('posted') or ''), reverse=True)[:max(0, quota-len(existing))]
        for j in selected:
            j.update(found=today, last_verified=now.isoformat(), run_id=run_id)
            j['letter_md'], j['letter_docx'] = letters.generate(j, profile, root, today)
            j['id'] = database.add(c, j); j['status'] = 'New'
            if j['source'] in checks: checks[j['source']].selected += 1
        check_rows = discovery.serialise_checks(notes)
        database.save_source_checks(c, run_id, check_rows)
        for row in check_rows:
            checks[row['source']].last_successful_check = row['last_successful_check']
        if hasattr(notes, 'refresh'): notes.refresh()
        notes.append(f'Quota: {quota} per run including retries; selected {len(selected)} new vacancies. No applications submitted.')
        report_rows = [j for j in database.jobs(c) if j.get('run_id') == run_id]
        output = reporting.report(root, today, report_rows, notes, run_id, source_checks=check_rows)
        failed = any(check.errors for check in checks.values()) or any(x.startswith('SOURCE FAILED') for x in notes)
        c.execute('UPDATE runs SET completed=?,diagnostics=? WHERE id=?',
                  (None if failed else datetime.now(ZoneInfo('Pacific/Auckland')).isoformat(), json.dumps(list(notes)), run_id))
        c.commit()
        print(output); print('Run:', run_id); print('New jobs:', len(selected))
        if failed:
            print('One or more sources failed; remaining sources completed. Inspect report.', file=sys.stderr)
            sys.exit(2)
    finally:
        c.close()

if __name__ == '__main__': main()
