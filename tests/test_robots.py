import time
import unittest

from jobs4jsr.robots import Rules, UnsupportedRule

AGENT = 'Jobs4JSR/0.2 (local personal vacancy research)'

# Trimmed from the real nz.seek.com/robots.txt (14 October 2026 research date).
SEEK = """# robots.txt file for nz.seek.com
User-agent: *
Disallow: */job/
Disallow: *?
Disallow: /graphql
Disallow: /api/jobsearch/
Allow: *?advertiserid
Allow: *?keywords
# Disallowed bots
User-agent: PetalBot
Disallow: /
"""

# Trimmed from the real www.trademe.co.nz/robots.txt.
TRADEME = """User-agent: *
Allow: /
Disallow: /a/
Allow: /a/jobs/*/listing
Allow: /a/jobs/*/auckland/auckland-city
Disallow: /a/*search?
Disallow: /a/*refine
"""


class MatchingTests(unittest.TestCase):
    def test_wildcard_and_anchor_are_honoured(self):
        rules = Rules.parse('User-agent: *\nDisallow: */job/\nDisallow: /exact$\n', AGENT)
        self.assertFalse(rules.can_fetch('https://nz.seek.com/job/93970581'))
        self.assertFalse(rules.can_fetch('https://nz.seek.com/a/b/job/1'))
        self.assertTrue(rules.can_fetch('https://nz.seek.com/jobs-in-hospitality/x'))
        self.assertFalse(rules.can_fetch('https://example.org/exact'))
        self.assertTrue(rules.can_fetch('https://example.org/exact/sub'))  # '$' anchors the end

    def test_longest_match_wins_and_allow_wins_a_tie(self):
        rules = Rules.parse('User-agent: *\nDisallow: /a/\nAllow: /a/jobs/*/listing\n', AGENT)
        self.assertFalse(rules.can_fetch('https://www.trademe.co.nz/a/marketplace'))
        self.assertTrue(rules.can_fetch('https://www.trademe.co.nz/a/jobs/it/auckland/listing/123'))
        tie = Rules.parse('User-agent: *\nDisallow: /same\nAllow: /same\n', AGENT)
        self.assertTrue(tie.can_fetch('https://example.org/same'))

    def test_empty_disallow_allows_everything_and_missing_file_allows_all(self):
        rules = Rules.parse('User-agent: *\nDisallow:\n', AGENT)
        self.assertTrue(rules.can_fetch('https://example.org/anything'))
        self.assertTrue(Rules.parse('', AGENT).can_fetch('https://example.org/anything'))

    def test_query_string_rules_use_the_path_and_query(self):
        rules = Rules.parse('User-agent: *\nDisallow: *?\nAllow: *?keywords\n', AGENT)
        self.assertTrue(rules.can_fetch('https://nz.seek.com/x?keywords=waiter'))
        self.assertFalse(rules.can_fetch('https://nz.seek.com/x?tracking=1'))

    def test_user_agent_group_selection_prefers_specific_then_star(self):
        rules = Rules.parse(SEEK, AGENT)
        self.assertTrue(rules.can_fetch('https://nz.seek.com/waiter-jobs/in-All-Auckland'))
        petal = Rules.parse(SEEK, 'PetalBot')
        self.assertFalse(petal.can_fetch('https://nz.seek.com/anything'))

    def test_seek_and_trademe_real_rules(self):
        seek = Rules.parse(SEEK, AGENT)
        self.assertFalse(seek.can_fetch('https://nz.seek.com/job/93970581?type=standard'))
        self.assertFalse(seek.can_fetch('https://nz.seek.com/api/jobsearch/v5/search'))
        self.assertFalse(seek.can_fetch('https://nz.seek.com/graphql'))
        self.assertTrue(seek.can_fetch('https://nz.seek.com/waiter-jobs-in-hospitality-tourism/in-All-Auckland'))
        trademe = Rules.parse(TRADEME, AGENT)
        self.assertTrue(trademe.can_fetch(
            'https://www.trademe.co.nz/a/jobs/hospitality-tourism/waiting-staff/auckland/auckland-city'))
        self.assertTrue(trademe.can_fetch(
            'https://www.trademe.co.nz/a/jobs/hospitality-tourism/waiting-staff/auckland/auckland-city/full-time/listing/6178405701'))
        self.assertFalse(trademe.can_fetch('https://www.trademe.co.nz/a/jobs/search?term=waiter'))

    def test_repeated_wildcards_collapse_instead_of_backtracking(self):
        # Trade Me's real robots.txt carries a rule with ~180 consecutive '*'.
        # Compiling one '.*' per '*' backtracks exponentially and hangs the client.
        hostile = 'User-agent: *\nDisallow: /a/' + '*' * 180 + 'k97.cc\nAllow: /a/jobs/x\n'
        rules = Rules.parse(hostile, AGENT)
        self.assertEqual(rules.group['rules'][0][2].core.count('*'), 1)
        started = time.monotonic()
        self.assertTrue(rules.can_fetch('https://www.trademe.co.nz/a/jobs/x'))
        self.assertTrue(rules.can_fetch('https://www.trademe.co.nz/a/anything-else'))  # hostile rule does not match
        self.assertFalse(rules.can_fetch('https://www.trademe.co.nz/a/foo/k97.cc'))  # hostile rule does match
        self.assertLess(time.monotonic() - started, 1.0)

    def test_separated_wildcards_match_in_bounded_time(self):
        # These cannot be collapsed, so the scan itself must stay bounded rather
        # than backtracking through every combination.
        pattern = 'User-agent: *\nDisallow: /' + '/'.join(['a*'] * 30) + 'b\n'
        rules = Rules.parse(pattern, AGENT)
        target = 'https://example.org/' + 'a/' * 300
        started = time.monotonic()
        for _ in range(20):
            self.assertTrue(rules.can_fetch(target))
        self.assertLess(time.monotonic() - started, 2.0)

    def test_unusable_rule_is_refused_rather_than_guessed(self):
        # Fail closed: a rule this client cannot evaluate safely is an error, and
        # the transport turns it into a refusal for that origin.
        with self.assertRaises(UnsupportedRule):
            Rules.parse('User-agent: *\nDisallow: /' + 'x*' * 40 + '\n', AGENT)
        with self.assertRaises(UnsupportedRule):
            Rules.parse('User-agent: *\nDisallow: /' + 'y' * 5000 + '\n', AGENT)

    def test_delay_and_rate_directives(self):
        rules = Rules.parse('User-agent: *\nAllow: /\nCrawl-delay: 4\nRequest-rate: 1/5\n', AGENT)
        self.assertEqual(rules.crawl_delay(), 4.0)
        self.assertEqual(rules.request_rate(), (1, 5))
        self.assertIsNone(Rules.parse('', AGENT).crawl_delay())
        self.assertIsNone(Rules.parse('User-agent: *\nRequest-rate: nope\n', AGENT).request_rate())


if __name__ == '__main__':
    unittest.main()
