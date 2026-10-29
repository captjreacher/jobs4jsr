"""Polite transport and fault-isolated employer discovery."""
import html
import re
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime
from urllib.parse import urljoin, urlsplit
from zoneinfo import ZoneInfo
import requests
from .robots import Rules, UnsupportedRule

AGENT = 'Jobs4JSR/0.2 (local personal vacancy research)'

class RateLimited(RuntimeError):
    """Stop this employer immediately instead of continuing to hit its pages."""

def plain(value):
    return re.sub(r'\s+', ' ', html.unescape(re.sub('<[^>]+>', ' ', html.unescape(value or '')))).strip()

class Client:
    def __init__(self, delay=1):
        self.session = requests.Session()
        self.rules = {}
        self.delay = max(1, delay)

    def rules_for(self, origin):
        """Fetch and parse one origin's robots.txt. A missing file allows all."""
        if origin not in self.rules:
            r = self.session.get(origin + '/robots.txt', timeout=25,
                                 headers={'User-Agent': AGENT}, allow_redirects=False)
            if r.status_code not in (200, 404):
                raise RuntimeError('Robots unavailable: ' + origin)
            try:
                self.rules[origin] = Rules.parse(r.text if r.status_code == 200 else '', AGENT)
            except UnsupportedRule as exc:
                # Fail closed: an unreadable rule is never treated as permission.
                raise RuntimeError('Robots rule unusable at ' + origin + ' (' + str(exc) + ')') from exc
        return self.rules[origin]

    def allowed(self, url):
        """True when robots.txt permits this URL. Used to skip, not to bypass."""
        u = urlsplit(url)
        if u.scheme not in ('http', 'https') or not u.netloc:
            return False
        return self.rules_for(u.scheme + '://' + u.netloc).can_fetch(url)

    def get(self, url):
        # Every redirect is checked BEFORE following it, including a new origin.
        for _ in range(6):
            u = urlsplit(url)
            if u.scheme not in ('http', 'https') or not u.netloc:
                raise ValueError('Invalid public URL')
            origin = u.scheme + '://' + u.netloc
            rules = self.rules_for(origin)
            if not rules.can_fetch(url):
                raise RuntimeError('Robots disallows ' + url)
            rate = rules.request_rate()
            rate_delay = rate[1] / rate[0] if rate and rate[0] else 0
            time.sleep(max(self.delay, rules.crawl_delay() or 0, rate_delay))
            r = self.session.get(url, timeout=25, headers={'User-Agent': AGENT}, allow_redirects=False)
            if r.status_code in (301, 302, 303, 307, 308):
                url = urljoin(url, r.headers['Location'])
                continue
            if r.status_code == 429:
                raise RateLimited('HTTP 429 at ' + origin + '; stop source, Retry-After=' +
                                  r.headers.get('Retry-After', 'unspecified'))
            r.raise_for_status()
            r.encoding = 'utf-8'
            return r.text
        raise RuntimeError('Too many redirects')

@dataclass
class SourceCheck:
    source: str
    checked_at: str
    status: str = 'success'
    inspected: int = 0
    verified: int = 0
    qualified: int = 0
    duplicates: int = 0
    selected: int = 0
    excluded: int = 0
    errors: list = field(default_factory=list)
    notes: list = field(default_factory=list)
    last_successful_check: str | None = None
    observations: dict = field(default_factory=dict)

    def error(self, message):
        self.errors.append(str(message))
        self.status = 'partial'

class DiscoveryNotes(list):
    def __init__(self, checks):
        self.checks = checks
        super().__init__()

    def refresh(self):
        self.clear()
        for check in self.checks:
            prefix = 'SOURCE FAILED ' if check.status == 'failed' else 'SOURCE PARTIAL ' if check.errors else ''
            self.append(f'{prefix}{check.source}: inspected {check.inspected}, verified {check.verified}, '
                        f'qualified {check.qualified}, duplicates {check.duplicates}, selected {check.selected}; '
                        f'last successful check {check.last_successful_check or "never"}.')
            self.extend(f'{check.source}: {note}' for note in check.notes)
            self.extend(f'{check.source}: ERROR {error}' for error in check.errors)
        self.append('Restricted job boards and blocked ATS endpoints are not scraped. '
                    'Unknown venue locations and incomplete adverts are excluded.')

def discover(settings, today, existing=()):
    from .adapters import ADAPTERS
    client = Client(settings.get('request_delay', 1))
    jobs, checks = [], []
    for source in settings['sources']:
        if not source.get('enabled', True):
            continue
        check = SourceCheck(source['name'], datetime.now(ZoneInfo('Pacific/Auckland')).isoformat())
        checks.append(check)
        try:
            adapter = ADAPTERS[source.get('adapter', 'star_group')]
            jobs.extend(adapter(client, source, settings, today, check))
            # Missing from a listing is not closure. Recheck its original advert explicitly.
            seen = {j.get('url') for j in jobs if j.get('source') == source['name']}
            from .adapters import detail
            for old in existing:
                if old['source'] == source['name'] and old['url'] not in seen:
                    check.inspected += 1
                    job = detail(client, source, settings, today, check, old['url'])
                    if job: jobs.append(job)
            if not check.errors:
                check.last_successful_check = check.checked_at
        except Exception as exc:
            check.status = 'failed'
            check.errors.append(str(exc))
    notes = DiscoveryNotes(checks)
    notes.refresh()
    return jobs, notes

def serialise_checks(notes):
    return [asdict(check) for check in getattr(notes, 'checks', [])]
