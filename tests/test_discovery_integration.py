import contextlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from jobs4jsr import cli, database, deduplication, discovery


class IntegrationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.root = Path(self.tmp.name)
        (self.root/'config').mkdir()
        (self.root/'config/settings.example.json').write_text('{}')
        private = self.root/'data/private'; private.mkdir(parents=True)
        self.profile = {'name': 'Example Candidate', 'skills': ['customer service'],
                        'experience': [{'role': 'Retail Assistant', 'employer': 'Example Store',
                                        'duties': ['welcomed customers', 'processed sales']}],
                        'style': {'greeting': 'Dear Recruitment Team', 'closing': 'Yours sincerely'}}
        (private/'jess_profile.json').write_text(json.dumps(self.profile))

    def tearDown(self): self.tmp.cleanup()

    def job(self, n, source='Employer A'):
        return {'vacancy_id': str(n), 'source': source, 'url': f'https://example.org/{n}',
                'employer': f'Example Venue {n}', 'title': 'Food & Beverage Attendant',
                'location': 'Auckland CBD', 'distance': 1, 'job_type': 'Part-time',
                'description': 'Customer service and communication in a team; training provided.',
                'posted': '2026-10-10', 'recent': True, 'uncertainties': ['Confirm availability']}

    def invoke(self, rows, notes, *arguments):
        with patch.object(sys, 'argv', ['jobs4jsr', '--root', str(self.root), *arguments]), \
             patch('jobs4jsr.cli.discovery.discover', return_value=(rows, notes)), \
             contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            cli.main()

    def connect(self): return database.connect(self.root/'data/private/jobs.sqlite3')

    def test_manual_run_does_not_consume_scheduled_slots(self):
        c = self.connect()
        c.execute("INSERT INTO runs(id,completed) VALUES('2026-10-12-scheduled','preserved')"); c.commit(); c.close()
        self.invoke([self.job(1)], [], 'search', '--run-id', 'live-check')
        self.invoke([self.job(2)], [], 'search', '--run-id', 'live-check')
        c = self.connect()
        self.assertEqual(c.execute('SELECT id,completed FROM runs WHERE id LIKE ? ORDER BY id', ('%-scheduled',)).fetchall(),
                         [('2026-10-12-scheduled', 'preserved')])
        self.assertEqual(len(database.jobs(c)), 1); c.close()

    def test_partial_run_retry_never_exceeds_three_recommendations(self):
        def notes():
            good = discovery.SourceCheck('Employer A', '2026-10-14T10:00:00+13:00', last_successful_check='2026-10-14T10:00:00+13:00')
            bad = discovery.SourceCheck('Employer B', '2026-10-14T10:00:00+13:00', status='failed', errors=['timeout'])
            result = discovery.DiscoveryNotes([good, bad]); result.refresh(); return result
        for _ in range(2):
            with self.assertRaises(SystemExit) as caught:
                self.invoke([self.job(n) for n in range(5)], notes(), 'scheduled')
            self.assertEqual(caught.exception.code, 2)
        c = self.connect()
        self.assertEqual(len(database.jobs(c)), 3)
        self.assertEqual(len(database.source_checks(c)), 2)
        self.assertEqual(database.source_checks(c)[1]['status'], 'failed'); c.close()

    def test_duplicates_in_batch_and_history_preserve_status_and_source(self):
        first = self.job(1); alternate = dict(first, source='Employer B', url='https://alternate.example/99',
                                            title='Food and Beverage Attendant', employer='Example Venue 1 (Group)',
                                            location='Auckland Central')
        notes = discovery.DiscoveryNotes([discovery.SourceCheck('Employer A', 'now'), discovery.SourceCheck('Employer B', 'now')])
        self.invoke([first, alternate], notes, 'search', '--run-id', 'first')
        self.assertEqual(notes.checks[1].duplicates, 1)
        c = self.connect(); database.status(c, database.jobs(c)[0]['id'], 'Applied'); c.close()
        self.invoke([alternate], [], 'search', '--run-id', 'second')
        c = self.connect(); jobs = database.jobs(c)
        self.assertEqual(len(jobs), 1)
        self.assertEqual(jobs[0]['status'], 'Applied')
        self.assertEqual(jobs[0]['url'], first['url'])
        self.assertEqual(jobs[0]['description'], first['description'])
        self.assertEqual(jobs[0]['alternate_sources'][0]['source'], 'Employer B')
        self.assertEqual(c.execute('SELECT COUNT(*) FROM status_history').fetchone()[0], 1); c.close()

    def test_source_last_success_survives_later_failure_and_db_upgrade(self):
        import sqlite3
        path = self.root/'legacy.sqlite3'; legacy = sqlite3.connect(path)
        legacy.execute('CREATE TABLE jobs(id INTEGER PRIMARY KEY, url TEXT UNIQUE, status TEXT NOT NULL, payload TEXT NOT NULL)')
        legacy.execute('INSERT INTO jobs VALUES(1,?,?,?)', ('https://example.org/old', 'Applied', json.dumps(self.job(1))))
        legacy.commit(); legacy.close()
        c = database.connect(path)
        successful = discovery.serialise_checks(discovery.DiscoveryNotes([
            discovery.SourceCheck('Employer A', '2026-10-14T10:00:00+13:00', last_successful_check='2026-10-14T10:00:00+13:00')]))
        database.save_source_checks(c, 'manual-first', successful)
        failed = discovery.serialise_checks(discovery.DiscoveryNotes([
            discovery.SourceCheck('Employer A', '2026-10-14T11:00:00+13:00', status='failed', errors=['timeout'])]))
        database.save_source_checks(c, 'manual-second', failed); c.commit()
        self.assertEqual(database.source_checks(c, 'manual-second')[0]['last_successful_check'], '2026-10-14T10:00:00+13:00')
        self.assertEqual(database.jobs(c)[0]['status'], 'Applied'); c.close()

    def test_shared_application_url_identifies_cross_source_copy(self):
        first = dict(self.job(1), application_url='https://applications.example/job/1?oga=true')
        other = dict(self.job(2, 'Employer B'), application_url='https://applications.example/job/1')
        self.assertTrue(deduplication.duplicate(first, other))

    def test_manual_id_cannot_escape_report_directory(self):
        with self.assertRaisesRegex(ValueError, 'Manual run ID'):
            self.invoke([], [], 'search', '--run-id', '../../escape')


if __name__ == '__main__': unittest.main()
