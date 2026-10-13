import json
import unittest
from unittest.mock import Mock, patch

from jobs4jsr import adapters, discovery, scoring

TODAY = '2026-10-14'


def posting(title='Waitress', employer='Example Hotel', description=None, **extra):
    item = {'@type': 'JobPosting', 'title': title,
            'description': description or 'Friendly customer service and teamwork at Example Hotel Auckland. Training provided.',
            'datePosted': '2026-10-10', 'identifier': {'value': '101'},
            'employmentType': ['Part-Time'],
            'jobLocation': {'address': {'addressLocality': employer + ', Auckland, New Zealand'}}}
    item.update(extra)
    return item


def page(item, action=True, graph=False):
    structured = {'@graph': [item]} if graph else item
    return '<script type="application/ld+json">' + json.dumps(structured) + '</script>' + (
        '<button id="top-apply-button">Apply</button>' if action else '')


def source(kind):
    return {'name': kind, 'adapter': kind, 'sitemap': 'https://example.org/sitemap.xml',
            'feed': 'https://example.org/feed', 'listing': 'https://example.org/careers/example/jobs',
            'company': 'example', 'locations': [
                {'match': ['Example Hotel', 'Auckland'], 'employer': 'Example Hotel',
                 'location': 'Auckland CBD', 'coordinates': [-36.8485, 174.7633],
                 'basis': 'Fictional test coordinate'}]}


def fake_client(responses):
    client = Mock()
    def get(url):
        value = responses[url]
        if isinstance(value, Exception): raise value
        return value
    client.get.side_effect = get
    return client


class AdapterTests(unittest.TestCase):
    def setUp(self):
        self.settings = {'centre': [-36.8485, 174.7633], 'venues': {}}
        self.check = discovery.SourceCheck('test', TODAY)

    def test_accor_sitemap_filters_other_cities_and_verifies_waitress(self):
        s = source('accor'); url = 'https://example.org/job/waitress-auckland-101'
        xml = '<urlset><url><loc>' + url + '</loc></url><url><loc>https://example.org/job/waiter-paris</loc></url></urlset>'
        c = fake_client({s['sitemap']: xml, url: page(posting(), graph=True)})
        jobs = adapters.accor(c, s, self.settings, TODAY, self.check)
        self.assertEqual(len(jobs), 1)
        self.assertEqual(jobs[0]['job_type'], 'Part-Time')
        self.assertEqual(jobs[0]['distance'], 0)
        self.assertEqual(self.check.inspected, 1)
        self.assertEqual(self.check.verified, 1)

    def test_accor_detail_failure_does_not_hide_next_vacancy(self):
        s = source('accor')
        first, second = ['https://example.org/job/waiter-auckland-' + n for n in ('1', '2')]
        xml = '<urlset>' + ''.join('<url><loc>' + u + '</loc></url>' for u in (first, second)) + '</urlset>'
        jobs = adapters.accor(fake_client({s['sitemap']: xml, first: RuntimeError('timeout'), second: page(posting())}),
                              s, self.settings, TODAY, self.check)
        self.assertEqual(len(jobs), 1)
        self.assertEqual(self.check.status, 'partial')
        self.assertIn('timeout', self.check.errors[0])

    def test_hind_public_feed_filters_other_cities(self):
        s = source('hind'); url = 'https://example.org/j/101'
        feed = {'jobs': [{'title': 'Food and Beverage Attendant', 'city': 'Auckland', 'url': url,
                          'application_url': url + '/apply', 'shortcode': '101'},
                         {'title': 'Waitress', 'city': 'Queenstown', 'url': 'https://example.org/j/102'}]}
        jobs = adapters.hind(fake_client({s['feed']: json.dumps(feed), url: page(posting('Food and Beverage Attendant'))}),
                             s, self.settings, TODAY, self.check)
        self.assertEqual(len(jobs), 1)
        self.assertEqual(jobs[0]['application_url'], url + '/apply')
        self.assertEqual(self.check.inspected, 2)

    def test_hind_rejects_changed_feed_schema(self):
        s = source('hind')
        with self.assertRaisesRegex(ValueError, 'jobs array'):
            adapters.hind(fake_client({s['feed']: '{}'}), s, self.settings, TODAY, self.check)

    def test_livehire_cafe_assistant_and_duplicate_cards(self):
        s = source('livehire'); path = '/careers/example/job/ABC/DEF/cafe-assistant'
        url = 'https://example.org' + path
        listing = f'<a href="{path}">Cafe Assistant</a><a href="{path}">More</a>'
        item = posting('Cafe Assistant', description='Example Hotel Auckland cafe team welcomes customer service experience and people keen to learn barista skills. Part-time role: 30 hours per week.')
        jobs = adapters.livehire(fake_client({s['listing']: listing, url: page(item)}),
                                 s, self.settings, TODAY, self.check)
        self.assertEqual(len(jobs), 1)
        self.assertEqual(self.check.inspected, 1)
        self.assertEqual(jobs[0]['hours'], '30 hours per week')
        self.assertIsNotNone(scoring.score(jobs[0], {'skills': ['customer service'], 'barista': False}))

    def test_livehire_detects_missing_cards_and_accepts_explicit_empty(self):
        s = source('livehire')
        with self.assertRaisesRegex(ValueError, 'format may have changed'):
            adapters.livehire(fake_client({s['listing']: '<html>JS shell</html>'}), s, self.settings, TODAY, self.check)
        self.assertEqual(adapters.livehire(fake_client({s['listing']: '<p>No current jobs</p>'}),
                         s, self.settings, TODAY, self.check), [])

    def test_expired_closed_missing_action_and_unknown_location(self):
        s = source('accor'); url = 'https://example.org/job/101'
        expired = posting(validThrough='2026-10-13')
        self.assertIsNone(adapters.normalise(expired, page(expired), url, s, self.settings, TODAY))
        item = posting()
        self.assertIsNone(adapters.normalise(item, page(item) + '<p>No longer accepting applications</p>', url, s, self.settings, TODAY))
        with self.assertRaisesRegex(ValueError, 'application action'):
            adapters.normalise(item, page(item, action=False), url, s, self.settings, TODAY)
        unknown = posting(employer='Unverified venue', description='Customer service and teamwork with training provided at an unknown location.')
        with self.assertRaisesRegex(ValueError, 'Unverified'):
            adapters.normalise(unknown, page(unknown), url, s, self.settings, TODAY)

    def test_radius_exact_not_rounded_and_future_dates(self):
        s = source('accor'); s['locations'][0]['coordinates'] = [-37.1, 174.7633]
        self.assertIsNone(adapters.normalise(posting(), page(posting()), 'https://example.org/job/101', s, self.settings, TODAY))
        s = source('accor'); item = posting(datePosted='2026-10-15')
        with self.assertRaisesRegex(ValueError, 'Future'):
            adapters.normalise(item, page(item), 'https://example.org/job/101', s, self.settings, TODAY)

    def test_source_failure_isolation_and_disabled_source(self):
        s = dict(self.settings, sources=[source('accor'), source('hind'), dict(source('livehire'), enabled=False)])
        with patch('jobs4jsr.adapters.ADAPTERS', {'accor': Mock(side_effect=RuntimeError('feed down')), 'hind': Mock(return_value=[{'title': 'Waitress'}])}):
            jobs, notes = discovery.discover(s, TODAY)
        self.assertEqual(len(jobs), 1)
        self.assertEqual(len(notes.checks), 2)
        self.assertEqual(notes.checks[0].status, 'failed')
        self.assertIsNone(notes.checks[0].last_successful_check)
        self.assertIsNotNone(notes.checks[1].last_successful_check)

    def test_all_requested_role_names_and_required_experience(self):
        for title in ('Waitress', 'Restaurant Server', 'Front-of-House', 'FOH', 'Food & Beverage Attendant',
                      'Food and Beverage Attendant', 'Hospitality Team Member', 'Cafe Assistant'):
            with self.subTest(title=title): self.assertTrue(scoring.target_role(title))
        j = {'title': 'Experienced Waiter', 'description': 'Waiting experience essential', 'distance': 1}
        self.assertIsNone(scoring.score(j, {'skills': ['customer service']}))
        self.assertFalse(scoring.target_role('Server Engineer'))
        self.assertFalse(scoring.target_role('Hospitality Sales Executive'))

    def test_brand_mention_cannot_override_non_auckland_address(self):
        item = posting(jobLocation={'address': {'addressLocality': 'Queenstown'}})
        with self.assertRaisesRegex(ValueError, 'Unverified'):
            adapters.normalise(item,page(item),'https://example.org/job/101',source('accor'),self.settings,TODAY)


class TransportTests(unittest.TestCase):
    def response(self, status, text='', headers=None):
        r = Mock(status_code=status, text=text, headers=headers or {})
        if status >= 400: r.raise_for_status.side_effect = RuntimeError(f'HTTP {status}')
        return r

    @patch('jobs4jsr.discovery.time.sleep')
    def test_robots_denial_prevents_page_request(self, sleep):
        c = discovery.Client(); c.session = Mock()
        c.session.get.return_value = self.response(200, 'User-agent: *\nDisallow: /private')
        with self.assertRaisesRegex(RuntimeError, 'Robots disallows'):
            c.get('https://example.org/private/jobs')
        self.assertEqual(c.session.get.call_count, 1)

    @patch('jobs4jsr.discovery.time.sleep')
    def test_redirect_destination_checked_before_fetch(self, sleep):
        c = discovery.Client(); c.session = Mock()
        c.session.get.side_effect = [self.response(200, 'User-agent: *\nAllow: /'),
            self.response(302, headers={'Location': 'https://restricted.example/job'}),
            self.response(200, 'User-agent: *\nDisallow: /')]
        with self.assertRaisesRegex(RuntimeError, 'Robots disallows'):
            c.get('https://example.org/job')
        self.assertEqual(c.session.get.call_count, 3)
        self.assertTrue(all(call.kwargs['allow_redirects'] is False for call in c.session.get.call_args_list))

    @patch('jobs4jsr.discovery.time.sleep')
    def test_rate_limit_and_robots_unavailable_fail_closed(self, sleep):
        c = discovery.Client(); c.session = Mock()
        c.session.get.side_effect = [self.response(200, 'User-agent: *\nAllow: /\nCrawl-delay: 4'), self.response(200, 'ok')]
        self.assertEqual(c.get('https://example.org/job'), 'ok')
        sleep.assert_called_with(4)
        c = discovery.Client(); c.session = Mock(); c.session.get.return_value = self.response(503)
        with self.assertRaisesRegex(RuntimeError, 'Robots unavailable'): c.get('https://example.org/job')

    @patch('jobs4jsr.discovery.time.sleep')
    def test_request_rate_and_http_429(self, sleep):
        c = discovery.Client(); c.session = Mock()
        c.session.get.side_effect = [self.response(200, 'User-agent: *\nAllow: /\nRequest-rate: 1/5'),
                                    self.response(429, headers={'Retry-After': '120'})]
        with self.assertRaisesRegex(discovery.RateLimited, 'Retry-After=120'):
            c.get('https://example.org/job')
        sleep.assert_called_with(5)
        self.assertEqual(c.session.get.call_count, 2)

    def test_rate_limit_stops_further_detail_requests(self):
        s = source('accor'); first = 'https://example.org/job/waiter-auckland-1'
        second = 'https://example.org/job/waiter-auckland-2'
        xml = '<urlset>' + ''.join('<url><loc>'+u+'</loc></url>' for u in (first,second)) + '</urlset>'
        client = fake_client({s['sitemap']: xml, first: discovery.RateLimited('HTTP 429')})
        with self.assertRaises(discovery.RateLimited):
            adapters.accor(client,s,{'centre':[0,0]},TODAY,discovery.SourceCheck('test',TODAY))
        self.assertEqual(client.get.call_count, 2)


if __name__ == '__main__': unittest.main()
