import re
import unicodedata
from urllib.parse import urlsplit,urlunsplit,parse_qsl,urlencode

def canonical(url):
    u=urlsplit(url)
    return urlunsplit((u.scheme.lower(),u.netloc.lower(),u.path.rstrip('/'),urlencode(sorted((k,v) for k,v in parse_qsl(u.query) if not k.startswith('utm_') and k not in {'trid','ref','source','oga'})),''))

def normalised(value):
    value = unicodedata.normalize('NFKD', value).encode('ascii', 'ignore').decode().lower()
    value = value.replace('&', ' and ')
    value = re.sub(r'\bfoh\b', 'front of house', value)
    value = re.sub(r'\bauckland central\b', 'auckland cbd', value)
    return re.sub(r'[^a-z0-9]+', ' ', value).strip()

def fingerprint(j):
    employer = re.sub(r'\s*\([^)]*\)\s*$', '', j['employer'])
    return '|'.join(normalised(value) for value in (employer,j['title'],j['location']))

def duplicate(j,old):
    urls = {canonical(j[key]) for key in ('url','application_url') if j.get(key)}
    old_urls = {canonical(old[key]) for key in ('url','application_url') if old.get(key)}
    if urls & old_urls: return True
    if fingerprint(j)!=fingerprint(old): return False
    # Different boards often assign different IDs and publication dates to one vacancy.
    # Treat a repost as new only with conservative same-provider evidence.
    from datetime import date
    try:
        gap=(date.fromisoformat(j['posted'])-date.fromisoformat(old['posted'])).days
    except (KeyError,TypeError,ValueError): gap=0
    proven_repost=bool(j.get('source') and j.get('source')==old.get('source') and j.get('vacancy_id') and old.get('vacancy_id') and j['vacancy_id']!=old['vacancy_id'] and gap>=30)
    return not proven_repost
