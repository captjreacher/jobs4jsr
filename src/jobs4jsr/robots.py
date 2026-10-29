"""Robots.txt rules with real wildcard semantics.

Python's ``urllib.robotparser`` compares a rule as a plain prefix and ignores
``*`` and ``$`` entirely. A directive such as SEEK's ``Disallow: */job/``
therefore never matches anything, and restricted advert pages would be fetched
anyway while the application still reported that it honoured robots.txt.

This module implements the matching the directives actually require:

* ``*`` matches any run of characters (including none);
* a trailing ``$`` anchors the match to the end of the path;
* every other character is literal;
* the longest matching pattern wins, and ``Allow`` wins a tie;
* an empty value (for example ``Disallow:``) matches everything.

User-agent groups are selected by the most specific matching product token, and
the ``*`` group is used when nothing more specific matches.

Matching never uses a regular expression. Wildcard globs are matched with the
standard greedy two-pointer scan, whose cost is bounded by
``len(pattern) * len(target)``. Compiling one ``.*`` per ``*`` instead lets a
hostile or careless rule backtrack exponentially: Trade Me's robots.txt carries
a directive with ~180 consecutive asterisks, which hung the crawler. Patterns
are also length- and wildcard-limited, and a rule outside those limits raises
instead of being guessed at, so the caller fails closed.
"""
import re
from urllib.parse import urlsplit

FIELDS = ('allow', 'disallow', 'crawl-delay', 'request-rate')

# Bounds. Real rules are a few dozen characters; these only reject abuse.
MAX_PATTERN = 4096
MAX_WILDCARDS = 32


class UnsupportedRule(ValueError):
    """A robots rule this client refuses to evaluate. Callers fail closed."""


class Pattern:
    """One rule value, matched without a regular expression."""

    __slots__ = ('core', 'anchored')

    def __init__(self, value):
        anchored = value.endswith('$')
        core = value[:-1] if anchored else value
        # '*' already means 'any characters', so '**' is equivalent and a run of
        # them can be collapsed without changing the rule.
        core = re.sub(r'\*+', '*', core)
        if len(core) > MAX_PATTERN:
            raise UnsupportedRule('rule longer than %d characters' % MAX_PATTERN)
        if core.count('*') > MAX_WILDCARDS:
            raise UnsupportedRule('rule has more than %d wildcards' % MAX_WILDCARDS)
        self.core = core
        self.anchored = anchored

    def matches(self, target):
        pattern = self.core if self.anchored else self.core + '*'
        index = position = 0
        star = -1
        mark = 0
        while index < len(target):
            if position < len(pattern) and pattern[position] == target[index]:
                index += 1
                position += 1
            elif position < len(pattern) and pattern[position] == '*':
                star = position
                mark = index
                position += 1
            elif star >= 0:
                position = star + 1
                mark += 1
                index = mark
            else:
                return False
        while position < len(pattern) and pattern[position] == '*':
            position += 1
        return position == len(pattern)


def _target(url):
    split = urlsplit(url)
    return split.path + (('?' + split.query) if split.query else '')


class Rules:
    """Parsed robots.txt rules for one origin."""

    def __init__(self, groups, agent):
        self.agent = agent
        self.group = None
        token = agent.split('/')[0].casefold()
        best = -1
        for group in groups:
            for candidate in group['agents']:
                if candidate and candidate != '*' and candidate in token and len(candidate) > best:
                    self.group, best = group, len(candidate)
        if self.group is None:
            self.group = next((group for group in groups if '*' in group['agents']), None)

    @classmethod
    def parse(cls, text, agent):
        groups, current = [], None
        for raw in text.splitlines():
            line = raw.split('#', 1)[0].strip()
            if not line or ':' not in line:
                continue
            field, _, value = line.partition(':')
            field, value = field.strip().lower(), value.strip()
            if field == 'user-agent':
                if current is None or current['started']:
                    current = {'agents': [], 'rules': [], 'started': False}
                    groups.append(current)
                current['agents'].append(value.casefold())
            elif field in FIELDS and current is not None:
                current['started'] = True
                current['rules'].append((field, value, Pattern(value)))
        return cls(groups, agent)

    def can_fetch(self, url):
        if self.group is None:
            return True
        target = _target(url)
        # Longest matching pattern wins; on equal length Allow beats Disallow.
        # A rule with an empty value is a no-op (e.g. 'Disallow:' means allow all).
        best = None
        for field, value, pattern in self.group['rules']:
            if field not in ('allow', 'disallow') or value == '':
                continue
            if pattern.matches(target):
                candidate = (len(value), field == 'allow')
                if best is None or candidate > best:
                    best = candidate
        return True if best is None else best[1]

    def _value(self, field):
        if self.group is None:
            return None
        return next((value for name, value, _ in self.group['rules'] if name == field), None)

    def crawl_delay(self):
        try:
            return float(self._value('crawl-delay'))
        except (TypeError, ValueError):
            return None

    def request_rate(self):
        value = self._value('request-rate')
        if not value:
            return None
        try:
            requests, seconds = (int(float(part)) for part in value.split('/')[:2])
        except ValueError:
            return None
        return (requests, seconds) if requests > 0 else None
