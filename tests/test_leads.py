import unittest
from unittest.mock import Mock

from jobs4jsr import database, leads

TRADEME_PAGE = 'https://www.trademe.co.nz/a/jobs/hospitality-tourism/waiting-staff/auckland/auckland-city'
SEEK_PAGE = 'https://nz.seek.com/waiter-jobs-in-hospitality-tourism/in-All-Auckland'

# Markup trimmed from the real Auckland City listing page (27 October 2026).
TRADEME_HTML = (
    '<a href="/a/jobs/hospitality-tourism/waiting-staff/auckland/auckland-city/full-time/listing/6189564448?rsqid=abc">'
    '<div tmid="title" class="tm-jobs-search-card__title">Waitstaff - Porch Bar &amp; Eatery</div>'
    '<time tmid="startDate" datetime="2026-10-20T20:42:08.733Z">6 days ago</time>'
    '<div tmid="company" class="jobs-search-card-metadata__company">Porch Bar &amp; Eatery</div>'
    '<div tmid="location" class="jobs-search-card-metadata__location">Auckland City, Auckland</div>'
    '<div tmid="subtitle" class="tm-jobs-search-card__short-description">Experienced Waitstaff required</div>'
    '<div tmid="approximatePayRange" class="tm-jobs-search-card__approximate-pay-range">$25 - $30 per hour</div>'
    '<span>Part-time, Permanent</span></a>'
    '<a href="/a/jobs/hospitality-tourism/waiting-staff/auckland/auckland-city/full-time/listing/6170000000">'
    '<div tmid="title" class="tm-jobs-search-card__title">Sous Chef</div>'
    '<div tmid="location" class="jobs-search-card-metadata__location">Auckland City, Auckland</div></a>'
)

# Markup trimmed from the real SEEK Auckland search page (27 October 2026).
SEEK_HTML = (
    '<article data-automation="premiumJob" data-testid="job-card" data-job-id="95445754">'
    '<a href="/job/95445754?type=promoted&amp;ref=search-standalone" data-automation="jobTitle">Waitstaff</a>'
    '<span data-automation="jobCompany">Private Advertiser</span>'
    '<span data-automation="jobLocation">Takapuna, Auckland</span>'
    '<span data-automation="jobShortDescription">Join a fast-paced team</span></article>'
    '<article data-testid="job-card" data-job-id="95555555">'
    '<a href="/job/95555555?type=standard" data-automation="jobTitle">Head Chef</a>'
    '<span data-automation="jobCompany">Bodega Eatery</span>'
    '<span data-automation="jobLocation">Henderson, Auckland</span></article>'
)


def client(pages, allowed=True):
    c = Mock()
    c.allowed.side_effect = lambda url: allowed
    c.get.side_effect = lambda url: pages[url]
    return c


class TradeMeLeadTests(unittest.TestCase):
    def setUp(self):
        self.source = {'name': 'Trade Me jobs', 'adapter': 'trademe_leads', 'pages': [TRADEME_PAGE]}
        self.check = Mock(inspected=0, excluded=0, notes=[])

    def test_cards_become_target_role_leads_with_clean_urls(self):
        found = leads.trademe(self.source, client({TRADEME_PAGE: TRADEME_HTML}), self.check)
        self.assertEqual(len(found), 1)  # Sous Chef is not a target role
        lead = found[0]
        self.assertEqual(lead['board'], 'Trade Me jobs')
        self.assertEqual(lead['advert_id'], '6189564448')
        self.assertEqual(lead['title'], 'Waitstaff - Porch Bar & Eatery')
        self.assertEqual(lead['employer'], 'Porch Bar & Eatery')
        self.assertEqual(lead['location'], 'Auckland City, Auckland')
        self.assertEqual(lead['posted'], '2026-10-20')
        self.assertEqual(lead['pay'], '$25 - $30 per hour')
        self.assertEqual(lead['job_type'], 'Part-time')
        self.assertTrue(lead['url'].endswith('/listing/6189564448'))
        self.assertNotIn('rsqid', lead['url'])
        self.assertEqual(self.check.inspected, 2)

    def test_senior_and_kitchen_titles_are_excluded_like_a_verified_vacancy(self):
        html = ''.join(
            '<a href="/a/jobs/hospitality-tourism/waiting-staff/auckland/auckland-city/full-time/listing/70%d">'
            '<div tmid="title" class="tm-jobs-search-card__title">%s</div>'
            '<div tmid="location" class="jobs-search-card-metadata__location">Auckland City, Auckland</div></a>'
            % (n, title)
            for n, title in enumerate(['Senior Waiter', 'Duty Manager', 'Kitchen Hand', 'Wait Staff']))
        found = leads.trademe(self.source, client({TRADEME_PAGE: html}), self.check)
        self.assertEqual([lead['title'] for lead in found], ['Wait Staff'])

    def test_changed_markup_fails_loudly(self):
        with self.assertRaisesRegex(ValueError, 'format may have changed'):
            leads.trademe(self.source, client({TRADEME_PAGE: '<html>JS shell</html>'}), self.check)

    def test_disallowed_page_is_skipped_without_fetching(self):
        c = client({}, allowed=False)
        self.assertEqual(leads.trademe(self.source, c, self.check), [])
        c.get.assert_not_called()
        self.assertIn('Robots disallows', self.check.notes[0])


class SeekLeadTests(unittest.TestCase):
    def setUp(self):
        self.source = {'name': 'SEEK NZ', 'adapter': 'seek_leads', 'pages': [SEEK_PAGE]}
        self.check = Mock(inspected=0, excluded=0, notes=[])

    def test_cards_become_leads_and_advert_url_is_never_fetched(self):
        c = client({SEEK_PAGE: SEEK_HTML})
        found = leads.seek(self.source, c, self.check)
        self.assertEqual(len(found), 1)  # Head Chef excluded
        lead = found[0]
        self.assertEqual(lead['title'], 'Waitstaff')
        self.assertEqual(lead['employer'], 'Private Advertiser')
        self.assertEqual(lead['location'], 'Takapuna, Auckland')
        self.assertEqual(lead['url'], 'https://nz.seek.com/job/95445754')
        self.assertEqual(c.get.call_args_list, [unittest.mock.call(SEEK_PAGE)])

    def test_card_without_an_advert_id_is_skipped(self):
        # No ID means no stable link and no way to deduplicate, so the card must
        # not become a lead that reappears as new on every run.
        html = ('<article data-testid="job-card"><span data-automation="jobTitle">Waitstaff</span>'
                '<span data-automation="jobCompany">Cafe</span></article>')
        found = leads.seek(self.source, client({SEEK_PAGE: html}), self.check)
        self.assertEqual(found, [])
        self.assertEqual(self.check.inspected, 1)
        self.assertIn('without an advert ID', self.check.notes[0])

    def test_leads_never_produce_a_score_or_letter(self):
        lead = leads.seek(self.source, client({SEEK_PAGE: SEEK_HTML}), self.check)[0]
        self.assertNotIn('match', lead)
        self.assertNotIn('distance', lead)
        self.assertNotIn('letter_docx', lead)


class LeadStorageTests(unittest.TestCase):
    def setUp(self):
        import tempfile
        from pathlib import Path
        self.root = Path(tempfile.mkdtemp())
        self.c = database.connect(self.root / 'jobs.sqlite3')

    def tearDown(self):
        self.c.close()

    def lead(self, advert_id):
        return {'board': 'SEEK NZ', 'advert_id': advert_id, 'title': 'Waitress',
                'employer': 'Example', 'location': 'Auckland CBD', 'url': 'https://nz.seek.com/job/' + advert_id,
                'summary': None, 'pay': None, 'job_type': None, 'posted': None, 'listed': None}

    def test_only_first_sighting_is_new(self):
        first = database.save_leads(self.c, [self.lead('1'), self.lead('2')], '2026-10-27-scheduled',
                                    '2026-10-27T02:00:00+13:00')
        self.c.commit()
        self.assertEqual(len(first), 2)
        second = database.save_leads(self.c, [self.lead('2'), self.lead('3')], '2026-10-28-scheduled',
                                     '2026-10-28T02:00:00+13:00')
        self.c.commit()
        self.assertEqual([l['advert_id'] for l in second], ['3'])
        stored = {l['advert_id']: l for l in database.leads(self.c)}
        self.assertEqual(len(stored), 3)
        self.assertEqual(stored['2']['first_seen'], '2026-10-27')
        self.assertEqual(stored['2']['first_seen_run'], '2026-10-27-scheduled')
        self.assertEqual([l['advert_id'] for l in database.leads(self.c, '2026-10-28-scheduled')], ['3'])

    def test_duplicate_and_unidentified_leads_are_stored_once(self):
        batch = [self.lead('1'), self.lead('1'), dict(self.lead('9'), advert_id=None)]
        new = database.save_leads(self.c, batch, '2026-10-27-scheduled', '2026-10-27T02:00:00+13:00')
        self.c.commit()
        self.assertEqual([l['advert_id'] for l in new], ['1'])
        self.assertEqual(len(database.leads(self.c)), 1)

    def test_stale_leads_leave_the_current_view_but_remain_for_audit(self):
        database.save_leads(self.c, [self.lead('1')], '2026-10-01-scheduled', '2026-10-01T02:00:00+13:00')
        database.save_leads(self.c, [self.lead('2')], '2026-10-27-scheduled', '2026-10-27T02:00:00+13:00')
        self.c.commit()
        current = database.leads(self.c, since='2026-10-06')
        self.assertEqual([l['advert_id'] for l in current], ['2'])
        self.assertEqual(current[0]['last_seen'], '2026-10-27T02:00:00+13:00')
        self.assertEqual(len(database.leads(self.c)), 2)  # history preserved

    def test_lead_counters_are_additive_to_an_existing_database(self):
        tables = {row[0] for row in self.c.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        self.assertIn('board_leads', tables)
        self.assertIn('jobs', tables)


if __name__ == '__main__':
    unittest.main()
