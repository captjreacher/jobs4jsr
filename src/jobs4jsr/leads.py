"""Best-effort, unverified job-board leads.

SEEK and Trade Me both forbid automated retrieval of some content, so these
sources deliberately read only the listing and search pages their robots.txt
permits and never fetch an individual advert page. A lead is therefore *not* a
vacancy: it has no verified workplace coordinate, no confirmed application
action and no complete advertisement. Leads never receive a score, a distance
or a generated letter, and they are never merged into the verified catalogue.

Indeed is not requested at all: a plain robots-obeying client receives HTTP 403
from its search pages, so no adapter is configured. Its saved-search link is
offered in the digest instead, for manual checking.
"""
import re
from urllib.parse import urljoin

from . import scoring
from .discovery import plain

JOB_TYPES = re.compile(r'\b(part[ -]time|full[ -]time|casual|contract|permanent|fixed[ -]term|temporary)\b', re.I)

# The same senior/management/kitchen exclusions scoring.score applies to a verified
# vacancy, so leads cannot surface roles the catalogue would have rejected.
EXCLUDED_TITLE = ('manager', 'senior', 'supervisor', 'leader', 'chef', 'kitchen hand')


def _field(html, name):
    match = re.search(r'tmid="' + name + r'"[^>]*>(?:\s*<[^>]+>)*\s*([^<]{1,300})', html)
    return plain(match.group(1)) if match else None


def _automation(html, name):
    match = re.search(r'data-automation="' + name + r'"[^>]*>([^<]{1,300})', html)
    return plain(match.group(1)) or None if match else None


def _posted(segment):
    match = re.search(r'tmid="startDate"[^>]*datetime="([^"]{10})', segment)
    return match.group(1) if match else None


def _segments(html, pattern):
    """Split a listing page on its card links so fields cannot leak between cards."""
    parts = pattern.split(html)
    for index in range(1, len(parts) - 2, 3):
        yield parts[index], parts[index + 1], parts[index + 2]


def _job_type(value):
    """Match the project's visible-employment-type wording, e.g. 'Part-time'."""
    return value.lower().replace(' ', '-').capitalize() if value else None


def _lead(board, advert_id, title, employer, location, posted, summary, pay, job_type, url):
    if not title or not scoring.target_role(title):
        return None
    if any(word in title.lower() for word in EXCLUDED_TITLE):
        return None
    return {'board': board, 'advert_id': advert_id, 'title': title, 'employer': employer,
            'location': location, 'posted': posted, 'listed': None, 'summary': summary,
            'pay': pay, 'job_type': job_type, 'url': url}


TRADEME_CARD = re.compile(r'href="(/a/jobs/[^"]*?/listing/(\d+))[^"]*"')


def trademe(source, client, check):
    leads = []
    for page in source.get('pages', []):
        if not client.allowed(page):
            check.notes.append('Robots disallows listing page; skipped without fetching: ' + page)
            continue
        html = client.get(page)
        found = False
        for path, advert_id, segment in _segments(html, TRADEME_CARD):
            found = True
            check.inspected += 1
            typed = JOB_TYPES.search(plain(segment))
            lead = _lead(source['name'], advert_id, _field(segment, 'title'), _field(segment, 'company'),
                         _field(segment, 'location'), _posted(segment), _field(segment, 'subtitle'),
                         _field(segment, 'approximatePayRange'), _job_type(typed.group(1)) if typed else None,
                         urljoin(page, path))
            if lead:
                leads.append(lead)
            else:
                check.excluded += 1
        if not found:
            raise ValueError('No Trade Me cards found; page format may have changed: ' + page)
    return leads


def seek(source, client, check):
    leads = []
    for page in source.get('pages', []):
        if not client.allowed(page):
            check.notes.append('Robots disallows search page; skipped without fetching: ' + page)
            continue
        html = client.get(page)
        found = unlinked = 0
        for attributes, content in re.findall(r'<article\b([^>]*)>(.*?)</article>', html, re.S):
            if 'data-testid="job-card"' not in attributes:
                continue
            found += 1
            check.inspected += 1
            identifier = re.search(r'data-job-id="(\d+)"', attributes)
            if not identifier:
                # Without an advert ID there is no stable link and no way to
                # deduplicate, so the card is skipped rather than stored as a
                # nameless duplicate on every run.
                unlinked += 1
                check.excluded += 1
                continue
            lead = _lead(source['name'], identifier.group(1),
                         _automation(content, 'jobTitle'), _automation(content, 'jobCompany'),
                         _automation(content, 'jobLocation'), None,
                         _automation(content, 'jobShortDescription'), None, None,
                         urljoin(page, '/job/' + identifier.group(1)))
            if lead:
                leads.append(lead)
            else:
                check.excluded += 1
        if unlinked:
            check.notes.append(f'{unlinked} card(s) skipped without an advert ID; they cannot be opened or deduplicated.')
        if not found:
            raise ValueError('No SEEK cards found; page format may have changed: ' + page)
    return leads


ADAPTERS = {'trademe_leads': trademe, 'seek_leads': seek}


def discover(settings):
    """Return (leads, messages). Lead problems never change the verified exit contract."""
    from datetime import datetime
    from zoneinfo import ZoneInfo
    from .discovery import Client, SourceCheck
    client = Client(settings.get('request_delay', 1))
    now = datetime.now(ZoneInfo('Pacific/Auckland')).isoformat()
    leads, messages = [], []
    for source in settings.get('lead_sources', []):
        if not source.get('enabled', True):
            continue
        check = SourceCheck(source['name'], now)
        try:
            found = ADAPTERS[source['adapter']](source, client, check)
        except Exception as exc:
            messages.append(f'LEAD SOURCE UNAVAILABLE {source["name"]}: {type(exc).__name__}: {exc}')
            continue
        leads.extend(found)
        messages.append(f'LEAD SOURCE {source["name"]}: inspected {check.inspected} cards, '
                        f'qualified {len(found)} target-role leads, excluded {check.excluded}.')
        messages.extend(f'LEAD SOURCE {source["name"]}: {note}' for note in check.notes)
    return leads, messages
