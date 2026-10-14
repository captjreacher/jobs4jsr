import json
import os
import unittest
from unittest.mock import patch
import requests
from jobs4jsr import database, discovery, sync
import test_discovery_integration as fixtures


class BoardTests(unittest.TestCase):
    setUp = fixtures.IntegrationTests.setUp
    tearDown = fixtures.IntegrationTests.tearDown
    job = fixtures.IntegrationTests.job
    invoke = fixtures.IntegrationTests.invoke
    connect = fixtures.IntegrationTests.connect

    def test_full_baseline_letters_only_top_three_and_stable_ids(self):
        self.invoke([self.job(n) for n in range(8)], [], 'baseline')
        c = self.connect()
        rows = database.jobs(c)
        self.assertEqual(len(rows), 8)
        self.assertEqual(sum(bool(j.get('letter_docx')) for j in rows), 3)
        ids = {j['url']: j['stable_id'] for j in rows}
        database.status(c, rows[0]['id'], 'Applied'); c.close()
        self.invoke([self.job(n) for n in range(8)], [], 'baseline')
        c = self.connect()
        self.assertEqual(ids, {j['url']: j['stable_id'] for j in database.jobs(c)})
        self.assertEqual(database.jobs(c)[0]['status'], 'Applied')
        self.assertEqual(sum(j['recommended'] for j in database.jobs(c)), 3)
        self.assertFalse(c.execute("SELECT 1 FROM runs WHERE id LIKE '%-scheduled'").fetchone())
        c.close()

    def test_failed_source_unknown_then_success_restores_open(self):
        self.invoke([self.job(1)], [], 'baseline')
        check = discovery.SourceCheck('Employer A', 'now', status='failed', errors=['timeout'])
        with self.assertRaises(SystemExit):
            self.invoke([], discovery.DiscoveryNotes([check]), 'search', '--run-id', 'outage')
        c = self.connect(); self.assertEqual(database.jobs(c)[0]['vacancy_state'], 'verification_unknown'); c.close()
        self.invoke([self.job(1)], [], 'search', '--run-id', 'recovered')
        c = self.connect(); j = database.jobs(c)[0]
        self.assertEqual(j['vacancy_state'], 'open'); self.assertNotIn('verification_warning', j); c.close()

    def test_explicit_closure_and_alternate_open_evidence(self):
        self.invoke([self.job(1)], [], 'baseline')
        check = discovery.SourceCheck('Employer A', 'now', observations={'https://example.org/1': 'closed'})
        self.invoke([], discovery.DiscoveryNotes([check]), 'search', '--run-id', 'closed')
        c = self.connect(); self.assertEqual(database.jobs(c)[0]['vacancy_state'], 'closed'); c.close()
        alternate = dict(self.job(1), source='Employer B', url='https://alternate.test/1')
        self.invoke([alternate], discovery.DiscoveryNotes([check]), 'search', '--run-id', 'alternate')
        c = self.connect(); self.assertEqual(database.jobs(c)[0]['vacancy_state'], 'open'); c.close()

    def test_additional_local_letter_on_request(self):
        self.invoke([self.job(n) for n in range(5)], [], 'baseline')
        c = self.connect(); missing = next(j for j in database.jobs(c) if not j.get('letter_docx')); c.close()
        self.invoke([], [], 'letters', '--job-id', str(missing['id']))
        c = self.connect(); j = next(j for j in database.jobs(c) if j['id'] == missing['id'])
        self.assertTrue((self.root / j['letter_docx']).exists()); c.close()

    def test_successful_feed_without_reverification_is_unknown_not_closed(self):
        self.invoke([self.job(1)], [], 'baseline')
        check=discovery.SourceCheck('Employer A','now')
        self.invoke([],discovery.DiscoveryNotes([check]),'search','--run-id','ambiguous')
        c=self.connect();self.assertEqual(database.jobs(c)[0]['vacancy_state'],'verification_unknown');c.close()

    def test_sync_retry_idempotency_decision_separation_and_privacy_gate(self):
        self.invoke([self.job(n) for n in range(4)], [], 'baseline')
        class Session:
            headers = {}
            def __init__(self): self.calls = []; self.fail = True
            def post(self, url, **options):
                self.calls.append((url, options))
                r = requests.Response(); r.status_code = 503 if self.fail and '/rest/' in url else 200
                r._content = json.dumps({'access_token': 'fictional-token'}).encode()
                return r
        session = Session(); c = self.connect()
        env = dict(JOBS4JSR_SUPABASE_URL='https://example.supabase.co', JOBS4JSR_PUBLISHABLE_KEY='fictional',
                   JOBS4JSR_SYNC_EMAIL='machine@example.test', JOBS4JSR_SYNC_PASSWORD='fictional',
                   JOBS4JSR_OWNER_ID='11111111-1111-1111-1111-111111111111', JOBS4JSR_LETTER_UPLOAD_APPROVED='false')
        with patch.dict(os.environ, env, clear=True):
            with self.assertRaises(RuntimeError): sync.publish(c, self.root, session)
            session.fail = False; sync.publish(c, self.root, session); sync.publish(c, self.root, session)
        self.assertFalse(any('/storage/' in u or 'decisions' in u for u, _ in session.calls))
        rows = [options['json'] for url, options in session.calls if 'jobs4jsr_jobs?' in url]
        self.assertEqual(rows[1:5], rows[5:9])
        self.assertNotIn('letters', rows[-1]); self.assertNotIn('description', rows[-1]['vacancy'])
        self.assertIn('why', rows[-1]['vacancy']); self.assertIn('source', rows[-1]['vacancy'])
        self.assertEqual(c.execute('SELECT status FROM sync_runs').fetchall(), [('failed',), ('success',), ('success',)])
        with patch.dict(os.environ, dict(env,JOBS4JSR_LETTER_UPLOAD_APPROVED='true'), clear=True):
            sync.publish(c,self.root,session)
        uploads=[(url,options) for url,options in session.calls if '/storage/' in url]
        self.assertEqual(len(uploads),6)
        self.assertTrue(all(options['headers']['x-upsert']=='true' for _,options in uploads))
        self.assertTrue(all('/jobs4jsr-letters/'+env['JOBS4JSR_OWNER_ID']+'/' in url for url,_ in uploads))
        c.close()

    def test_missing_sync_credentials_fail_without_network(self):
        c = self.connect()
        with patch.dict(os.environ, {}, clear=True), patch('requests.Session') as session:
            with self.assertRaises(ValueError): sync.publish(c, self.root)
            session.assert_not_called()
        c.close()
