"""Read-only adapters for public employer feeds and structured advertisements."""
import json
import re
import xml.etree.ElementTree as ET
from datetime import date
from html.parser import HTMLParser
from urllib.parse import urljoin, urlsplit
import requests

from .discovery import RateLimited, plain
from .scoring import distance, target_role


class Page(HTMLParser):
    def __init__(self, text):
        super().__init__(convert_charrefs=True)
        self.links, self.postings = [], []
        self.script, self.chunks = False, []
        self.apply = False
        self.feed(text)

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == 'a' and attrs.get('href'):
            self.links.append(attrs['href'])
        if tag == 'script':
            self.script = attrs.get('type', '').lower() == 'application/ld+json'
            self.chunks = []
        if tag in ('a', 'button', 'input'):
            marker = ' '.join(str(attrs.get(key, '')) for key in ('class', 'id', 'value', 'aria-label'))
            if re.search(r'(jobApplyBtn|(?:top-|job-)?apply-button|\bapply\b)', marker, re.I):
                self.apply = True

    def handle_data(self, data):
        if self.script:
            self.chunks.append(data)

    def handle_endtag(self, tag):
        if tag == 'script' and self.script:
            self.postings.extend(job_postings(json.loads(''.join(self.chunks))))
            self.script = False


def job_postings(data):
    if isinstance(data, list):
        return [record for item in data for record in job_postings(item)]
    if isinstance(data, dict):
        types = data.get('@type', [])
        if types == 'JobPosting' or isinstance(types, list) and 'JobPosting' in types:
            return [data]
        return job_postings(data.get('@graph', []))
    return []


def metadata(item, key):
    value = item.get(key)
    return ', '.join(value) if isinstance(value, list) else value


def location_for(item, source, settings, description):
    locations = item.get('jobLocation', [])
    locations = locations if isinstance(locations, list) else [locations]
    if len(locations) != 1:
        raise ValueError('Missing or multiple work locations; needs review')
    address = locations[0].get('address', {})
    text = plain(' '.join(str(address.get(k, '')) for k in
                          ('streetAddress', 'addressLocality', 'addressRegion', 'addressCountry')))
    if 'auckland' not in text.casefold():
        raise ValueError('Unverified/ambiguous work location: ' + text)
    candidates = []
    for mapping in source.get('locations', []):
        evidence = text + ' ' + description
        if all(token.casefold() in evidence.casefold() for token in mapping['match']):
            candidates.append(mapping)
    if len(candidates) == 1:
        return candidates[0]
    if source.get('adapter', 'star_group') == 'star_group':
        venue = address.get('streetAddress', '')
        mapped = settings['venues'].get(venue)
        if mapped:
            return dict(mapped, employer=mapped.get('employer', venue) + ' (Star Group)')
    raise ValueError('Unverified/ambiguous work location: ' + text)


def normalise(item, page, url, source, settings, today, *, fallback_id=None, application_url=None):
    title = plain(item.get('title', ''))
    description = plain(item.get('description', ''))
    if not title or len(description) < 50:
        raise ValueError('Missing title or complete description')
    expires = item.get('validThrough')
    if expires and expires[:10] < today:
        return None
    visible = plain(re.sub(r'<(script|style)\b[^>]*>.*?</\1>', '', page, flags=re.S | re.I))
    if re.search(r'(position (?:is|has been) filled|no longer accepting applications|vacancy closed|job has expired)', visible, re.I):
        return None
    parsed = Page(page)
    if not parsed.apply and 'loading application form' not in visible.lower():
        raise ValueError('No live application action')
    if not application_url:
        application_url = next((href for href in parsed.links
                                if urlsplit(href).netloc == 'jobs.smartrecruiters.com'), None)
    geo = location_for(item, source, settings, description)
    km = distance(settings['centre'], geo['coordinates'])
    if km > 10:
        return None
    identifier = item.get('identifier', {})
    identifier = identifier.get('value') if isinstance(identifier, dict) else identifier
    posted = (item.get('datePosted') or '')[:10] or None
    if posted and date.fromisoformat(posted) > date.fromisoformat(today):
        raise ValueError('Future publication date; needs review')
    visible_type = re.search(r'Employment Type\s+(Casual|Part-time(?:, Full-time)?|Full-time)', visible, re.I)
    job_type = visible_type.group(1) if visible_type else metadata(item, 'employmentType') or 'Unknown'
    if job_type == 'Unknown':
        found_type = re.search(r'\b(part[ -]time|full[ -]time|casual)\b', description, re.I)
        if found_type:
            job_type = found_type.group(1).capitalize()
    hours = re.search(r'\b(\d+(?:\s*[-–]\s*\d+)?)\s+hours per week\b', description, re.I)
    uncertainty = ['Confirm availability, work eligibility and shift requirements; table service training needed',
                   'Distance is approximate; employer advert must be checked before applying']
    if expires and date.fromisoformat(expires[:10]).year > date.fromisoformat(today).year + 2:
        uncertainty.append('Advert uses a far-future expiry placeholder; openness relies on the current listing and application action')
    return dict(vacancy_id=str(identifier or fallback_id or urlsplit(url).path.rsplit('/', 1)[-1]),
                source=source['name'], url=url, application_url=application_url or url,
                employer=geo['employer'], title=title, location=geo['location'],
                coordinates=geo['coordinates'], coordinate_basis=geo['basis'], distance=round(km, 2),
                job_type=job_type, structured_job_type=metadata(item, 'employmentType'), posted=posted,
                recent=bool(posted and 0 <= (date.fromisoformat(today) - date.fromisoformat(posted)).days <= 30),
                description=description, salary=None, hours=hours.group(0) if hours else None,
                active_evidence='Current employer listing, complete JobPosting and live application action',
                uncertainties=uncertainty)


def detail(client, source, settings, today, check, url, **kwargs):
    try:
        page = client.get(url)
        visible = plain(re.sub(r'<(script|style)\b[^>]*>.*?</\1>', '', page, flags=re.S|re.I))
        if re.search(r'no longer accepting applications|vacancy closed|job has expired|position (?:is|has been) filled',visible,re.I):
            check.observations[url]='closed'
            check.excluded+=1
            return None
        records = Page(page).postings
        if len(records) != 1:
            raise ValueError('Expected one specific JobPosting')
        if not target_role(records[0].get('title', '')):
            check.excluded += 1
            return None
        job = normalise(records[0], page, url, source, settings, today, **kwargs)
        if job:
            check.verified += 1
        else:
            check.excluded += 1
            visible = plain(re.sub(r'<(script|style)\b[^>]*>.*?</\1>', '', page, flags=re.S|re.I))
            expired = records[0].get('validThrough', '')[:10]
            if (expired and expired < today) or re.search(r'no longer accepting applications|vacancy closed|job has expired|position (?:is|has been) filled',visible,re.I):
                check.observations[url] = 'closed'
        return job
    except RateLimited:
        raise
    except requests.HTTPError as exc:
        if exc.response is not None and exc.response.status_code in (404,410):
            check.observations[url] = 'closed'
            check.notes.append('Confirmed unavailable advert: '+url)
        else: check.error(f'{url}: {exc}')
    except ValueError as exc:
        if str(exc).startswith('Unverified/ambiguous'):
            check.excluded += 1
            check.notes.append(str(exc))
        else:
            check.error(f'{url}: {exc}')
    except Exception as exc:
        check.error(f'{url}: {exc}')
    return None


def sitemap_jobs(client, source, settings, today, check):
    tree = ET.fromstring(client.get(source['sitemap']))
    if tree.tag.rsplit('}', 1)[-1] != 'urlset':
        raise ValueError('Expected vacancy URL sitemap, not sitemap index')
    urls = sorted(set(element.text for element in tree.iter()
                      if element.tag.endswith('loc') and element.text))
    jobs = []
    for url in urls:
        if urlsplit(url).netloc != urlsplit(source['sitemap']).netloc:
            continue
        slug = urlsplit(url).path.lower()
        if '/job' not in slug:
            continue
        if source.get('adapter') == 'accor' and 'auckland' not in slug:
            continue
        if not target_role(slug.replace('-', ' ')):
            continue
        check.inspected += 1
        job = detail(client, source, settings, today, check, url)
        if job:
            jobs.append(job)
    return jobs


def star_group(client, source, settings, today, check):
    return sitemap_jobs(client, source, settings, today, check)


def accor(client, source, settings, today, check):
    return sitemap_jobs(client, source, settings, today, check)


def hind(client, source, settings, today, check):
    feed = json.loads(client.get(source['feed']))
    if not isinstance(feed.get('jobs'), list):
        raise ValueError('Workable feed missing jobs array')
    jobs = []
    for item in feed['jobs']:
        check.inspected += 1
        if not target_role(item.get('title', '')) or 'auckland' not in str(item.get('city', '')).lower():
            check.excluded += 1
            continue
        url = item['url']
        if urlsplit(url).netloc != urlsplit(source['feed']).netloc:
            check.error('Unexpected Workable detail origin')
            continue
        job = detail(client, source, settings, today, check, url,
                     fallback_id=item.get('shortcode'), application_url=item.get('application_url'))
        if job:
            jobs.append(job)
    return jobs


def livehire(client, source, settings, today, check):
    listing = client.get(source['listing'])
    urls = sorted(set(urljoin(source['listing'], href) for href in Page(listing).links
                      if '/careers/' + source['company'] + '/job/' in href))
    if not urls and 'no current' not in plain(listing).lower() and 'no jobs' not in plain(listing).lower():
        raise ValueError('No vacancy cards or explicit empty-state; page format may have changed')
    jobs = []
    for url in urls:
        if urlsplit(url).netloc != urlsplit(source['listing']).netloc:
            continue
        check.inspected += 1
        if not target_role(urlsplit(url).path.rsplit('/', 1)[-1].replace('-', ' ')):
            check.excluded += 1
            continue
        job = detail(client, source, settings, today, check, url,
                     fallback_id='-'.join(urlsplit(url).path.split('/')[-3:-1]))
        if job:
            jobs.append(job)
    return jobs


ADAPTERS = {'star_group': star_group, 'accor': accor, 'hind': hind, 'livehire': livehire}
