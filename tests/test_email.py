import json
import os
import ssl
import tempfile
import unittest
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

from jobs4jsr import cli, database, emailer

TODAY = datetime(2026, 10, 27)  # Tuesday
ENV = {'JOBS4JSR_SMTP_HOST': 'smtp.example.test', 'JOBS4JSR_SMTP_PORT': '587',
       'JOBS4JSR_SMTP_SECURITY': 'starttls',
       'JOBS4JSR_SMTP_USER': 'owner@example.test', 'JOBS4JSR_SMTP_PASSWORD': 'fictional-app-password',
       'JOBS4JSR_DIGEST_TO': 'owner@example.test'}


def job(match=80, found='2026-10-27', url='https://example.test/job/1'):
    return {'employer': 'Example Hotel', 'title': 'Waitstaff', 'location': 'Auckland CBD',
            'distance': 1.2, 'job_type': 'Part-time', 'salary': None, 'hours': None,
            'pay': None, 'url': url, 'match': match, 'found': found}


def lead(advert_id='1', first_seen='2026-10-27'):
    return {'board': 'SEEK NZ', 'advert_id': advert_id, 'title': 'Waiter', 'employer': 'Cafe',
            'location': 'Ponsonby, Auckland', 'pay': '$25 - $30 per hour', 'job_type': None,
            'posted': None, 'listed': '2 days ago', 'summary': None,
            'url': 'https://nz.seek.com/job/' + advert_id, 'first_seen': first_seen}


def groups(*items):
    return [{'day': day, 'jobs': jobs, 'leads': leads} for day, jobs, leads in items]


class DigestContentTests(unittest.TestCase):
    def test_verified_vacancies_and_leads_are_labelled_separately(self):
        subject, text, body = emailer.build(TODAY, groups((TODAY, [job()], [lead()])))
        self.assertIn('2 new roles', subject)
        self.assertIn('Tuesday 27 October 2026', subject)
        self.assertIn('1 newly retained vacancy', text)
        self.assertIn('1 unverified lead(s)', text)
        self.assertIn('no advert was fetched', text)
        self.assertIn('unverified leads', body)
        self.assertIn('View advertisement', body)
        self.assertIn('Open listing', body)
        self.assertIn('Indeed NZ', text)  # offered for manual checking only

    def test_single_role_uses_singular_subject(self):
        subject, _, _ = emailer.build(TODAY, groups((TODAY, [job()], [])))
        self.assertIn('1 new role —', subject)

    def test_html_is_escaped(self):
        hostile = dict(job(), employer='<script>alert(1)</script>')
        _, _, body = emailer.build(TODAY, groups((TODAY, [hostile], [])))
        self.assertNotIn('<script>alert(1)</script>', body)
        self.assertIn('&lt;script&gt;', body)

    def test_catch_up_never_presents_an_earlier_role_as_new(self):
        subject, text, body = emailer.build(TODAY, groups(
            (date(2026, 10, 26), [job(found='2026-10-26', url='https://example.test/job/2')], []),
            (TODAY.date(), [job()], [])))
        self.assertIn('catching up on 26 October', subject)
        self.assertIn('Recorded on Monday 26 October 2026 — found by that day\'s search, not today:', text)
        self.assertIn('Recorded on Monday 26 October 2026', body)
        self.assertIn('A scheduled digest was missed', text)


class DigestSendTests(unittest.TestCase):
    @staticmethod
    def server():
        server = MagicMock()
        server.__enter__.return_value = server
        return server

    def test_unconfigured_email_refuses_instead_of_inventing_credentials(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertFalse(emailer.configured())
            with self.assertRaisesRegex(ValueError, 'not configured'):
                emailer.send('s', 't', '<p>h</p>')

    def test_starttls_login_and_send(self):
        server = self.server()
        with patch.dict(os.environ, ENV, clear=True), \
                patch('jobs4jsr.emailer.smtplib.SMTP', return_value=server) as smtp:
            emailer.send('Subject', 'text body', '<p>html</p>')
        smtp.assert_called_once()
        args, kwargs = smtp.call_args
        self.assertEqual(args, ('smtp.example.test', 587))
        self.assertEqual(kwargs['timeout'], 30)
        # The verified context is handed to starttls, never to a plain socket.
        self.assertNotIn('context', kwargs)
        context = server.starttls.call_args.kwargs['context']
        self.assertTrue(context.check_hostname)
        self.assertEqual(context.verify_mode, ssl.CERT_REQUIRED)
        server.starttls.assert_called_once_with(context=context)
        server.login.assert_called_once_with('owner@example.test', 'fictional-app-password')
        message = server.send_message.call_args[0][0]
        self.assertEqual(message['To'], 'owner@example.test')
        self.assertEqual(message['Subject'], 'Subject')
        self.assertIn('html', message.get_body(preferencelist=('html',)).get_content())

    def test_ssl_uses_the_encrypted_transport_and_verified_context(self):
        server = self.server()
        with patch.dict(os.environ, dict(ENV, JOBS4JSR_SMTP_SECURITY='ssl'), clear=True), \
                patch('jobs4jsr.emailer.smtplib.SMTP_SSL', return_value=server) as smtp:
            emailer.send('S', 't', '<p>h</p>')
        smtp.assert_called_once()
        args, kwargs = smtp.call_args
        self.assertEqual(args, ('smtp.example.test', 587))
        self.assertTrue(kwargs['context'].check_hostname)
        self.assertEqual(kwargs['context'].verify_mode, ssl.CERT_REQUIRED)
        server.starttls.assert_not_called()
        server.login.assert_called_once()

    def test_mode_is_case_insensitive_but_never_guessed(self):
        server = self.server()
        with patch.dict(os.environ, dict(ENV, JOBS4JSR_SMTP_SECURITY=' STARTTLS '), clear=True), \
                patch('jobs4jsr.emailer.smtplib.SMTP', return_value=server):
            emailer.send('S', 't', '<p>h</p>')
        server.starttls.assert_called_once()

    def test_unsupported_or_missing_security_never_sends_credentials(self):
        # 'plain', 'none' and near-misses must not fall through to an
        # unencrypted connection: the old code logged in over cleartext for them.
        for value in ('plain', 'none', 'tls', 'startls', 'SSLv3', 'required'):
            with self.subTest(security=value):
                with patch.dict(os.environ, dict(ENV, JOBS4JSR_SMTP_SECURITY=value), clear=True), \
                        patch('jobs4jsr.emailer.smtplib.SMTP') as smtp, \
                        patch('jobs4jsr.emailer.smtplib.SMTP_SSL') as smtps:
                    with self.assertRaisesRegex(ValueError, 'Unsupported SMTP security'):
                        emailer.send('S', 't', '<p>h</p>')
                    smtp.assert_not_called()
                    smtps.assert_not_called()

    def test_missing_security_setting_is_rejected(self):
        env = {name: value for name, value in ENV.items() if name != 'JOBS4JSR_SMTP_SECURITY'}
        with patch.dict(os.environ, env, clear=True):
            self.assertFalse(emailer.configured())
            with self.assertRaisesRegex(ValueError, 'not configured'):
                emailer.send('S', 't', '<p>h</p>')


class DigestCommandTests(unittest.TestCase):
    """The weekday evening task emails only when discovery produced new roles."""

    def setUp(self):
        self.root = Path(tempfile.mkdtemp())
        self.c = database.connect(self.root / 'jobs.sqlite3')
        self.now = datetime.now(timezone.utc)

    def tearDown(self):
        self.c.close()

    def store(self, found='2026-10-27', url='https://example.test/job/1'):
        self.c.execute('INSERT INTO jobs(url,status,payload) VALUES(?,?,?)',
                       (url, 'New', json.dumps(job(found=found, url=url))))
        self.c.commit()

    def store_lead(self, advert_id='1', first_seen='2026-10-27'):
        database.save_leads(self.c, [lead(advert_id, first_seen)], first_seen + '-scheduled',
                            first_seen + 'T02:00:00+13:00')
        self.c.commit()

    def state(self, day='2026-10-27'):
        return self.c.execute('SELECT state FROM digest_sends WHERE day=?', (day,)).fetchone()

    def test_quiet_weekday_sends_nothing(self):
        with patch('jobs4jsr.cli.emailer.send') as send:
            cli.digest(self.c, TODAY.date())
        send.assert_not_called()
        self.assertEqual(self.state(), ('skipped',))

    def test_new_roles_are_emailed(self):
        self.store()
        self.store_lead()
        with patch.dict(os.environ, ENV, clear=True), patch('jobs4jsr.cli.emailer.send') as send:
            cli.digest(self.c, TODAY.date())
        subject, text, body = send.call_args[0]
        self.assertIn('2 new roles', subject)
        self.assertEqual(self.state(), ('sent',))
        self.assertEqual(database.digest_sent(self.c, '2026-10-27')[2], 1)

    def test_the_same_day_is_never_emailed_twice(self):
        self.store()
        with patch.dict(os.environ, ENV, clear=True), patch('jobs4jsr.cli.emailer.send') as send:
            cli.digest(self.c, TODAY.date())
            self.assertEqual(send.call_count, 1)
            cli.digest(self.c, TODAY.date())  # the evening task retries
        self.assertEqual(send.call_count, 1)

    def test_a_day_already_delivered_is_not_repeated(self):
        self.store(found='2026-10-26')
        database.record_digest_day(self.c, '2026-10-26', 'sent', '2026-10-26T18:00:00+13:00', 1, 0)
        with patch.dict(os.environ, ENV, clear=True), patch('jobs4jsr.cli.emailer.send') as send:
            cli.digest(self.c, TODAY.date())
        send.assert_not_called()

    def test_a_missed_weekday_is_caught_up_and_labelled(self):
        self.store(found='2026-10-26', url='https://example.test/job/2')
        self.store()
        with patch.dict(os.environ, ENV, clear=True), patch('jobs4jsr.cli.emailer.send') as send:
            cli.digest(self.c, TODAY.date())
        subject, text, _ = send.call_args[0]
        self.assertIn('catching up on 26 October', subject)
        self.assertIn('Recorded on Monday 26 October 2026', text)
        self.assertEqual(self.state('2026-10-26'), ('sent',))
        self.assertEqual(self.state('2026-10-27'), ('sent',))

    def test_catch_up_is_bounded(self):
        # 16 October is far outside the two-weekday window and stays unsent.
        self.store(found='2026-10-16', url='https://example.test/job/3')
        with patch.dict(os.environ, ENV, clear=True), patch('jobs4jsr.cli.emailer.send') as send:
            cli.digest(self.c, TODAY.date())
        send.assert_not_called()
        self.assertIsNone(self.state('2026-10-16'))

    def test_a_live_claim_blocks_a_second_runner(self):
        self.store()
        database.claim_digest(self.c, '2026-10-27', 'other-run', now=self.now)
        with patch.dict(os.environ, ENV, clear=True), patch('jobs4jsr.cli.emailer.send') as send:
            cli.digest(self.c, TODAY.date())
        send.assert_not_called()
        self.assertEqual(self.state(), ('claimed',))
        self.assertEqual(database.digest_attempts(self.c, '2026-10-27'), 1)

    def test_a_crashed_claim_expires_and_is_retried_once(self):
        self.store()
        database.claim_digest(self.c, '2026-10-27', 'crashed-run',
                             now=self.now - timedelta(seconds=database.LEASE_SECONDS + 60))
        with patch.dict(os.environ, ENV, clear=True), patch('jobs4jsr.cli.emailer.send') as send:
            cli.digest(self.c, TODAY.date())
        self.assertEqual(send.call_count, 1)
        self.assertEqual(self.state(), ('sent',))
        self.assertEqual(database.digest_attempts(self.c, '2026-10-27'), 2)
        with patch.dict(os.environ, ENV, clear=True), patch('jobs4jsr.cli.emailer.send') as again:
            cli.digest(self.c, TODAY.date())
        again.assert_not_called()

    def test_a_failed_send_is_recorded_and_retried(self):
        self.store()
        with patch.dict(os.environ, ENV, clear=True), \
                patch('jobs4jsr.cli.emailer.send', side_effect=OSError('smtp refused')):
            with self.assertRaisesRegex(OSError, 'smtp refused'):
                cli.digest(self.c, TODAY.date())
        row = self.c.execute('SELECT state,error FROM digest_sends WHERE day=?', ('2026-10-27',)).fetchone()
        self.assertEqual(row[0], 'failed')
        self.assertIn('smtp refused', row[1])
        with patch.dict(os.environ, ENV, clear=True), patch('jobs4jsr.cli.emailer.send') as send:
            cli.digest(self.c, TODAY.date())
        self.assertEqual(send.call_count, 1)
        self.assertEqual(self.state(), ('sent',))

    def test_new_roles_without_configuration_fail_loudly(self):
        self.store()
        with patch.dict(os.environ, {}, clear=True), patch('jobs4jsr.cli.emailer.send') as send:
            with self.assertRaisesRegex(ValueError, 'not configured'):
                cli.digest(self.c, TODAY.date())
        send.assert_not_called()
        self.assertIsNone(self.state())

    def test_status_lists_recent_outcomes(self):
        self.store()
        with patch.dict(os.environ, ENV, clear=True), patch('jobs4jsr.cli.emailer.send'):
            cli.digest(self.c, TODAY.date())
        status = database.digest_status(self.c)
        self.assertEqual(status[0]['day'], '2026-10-27')
        self.assertEqual(status[0]['state'], 'sent')
        self.assertEqual(status[0]['jobs'], 1)


if __name__ == '__main__':
    unittest.main()
