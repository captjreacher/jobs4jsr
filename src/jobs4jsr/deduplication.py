import re
from urllib.parse import urlsplit,urlunsplit,parse_qsl,urlencode

def canonical(url):
    u=urlsplit(url)
    return urlunsplit((u.scheme.lower(),u.netloc.lower(),u.path.rstrip('/'),urlencode(sorted((k,v) for k,v in parse_qsl(u.query) if not k.startswith('utm_') and k not in {'trid','ref','source'})),''))

def fingerprint(j):
    return '|'.join(re.sub(r'[^a-z0-9]+',' ',j[x].lower()).strip() for x in ('employer','title','location'))

def duplicate(j,old):
    if canonical(j['url'])==canonical(old['url']): return True
    if fingerprint(j)!=fingerprint(old): return False
    # Different boards often assign different IDs and publication dates to one vacancy.
    # Treat a repost as new only with conservative same-provider evidence.
    from datetime import date
    try:
        gap=(date.fromisoformat(j['posted'])-date.fromisoformat(old['posted'])).days
    except (KeyError,TypeError,ValueError): gap=0
    proven_repost=bool(j.get('source') and j.get('source')==old.get('source') and j.get('vacancy_id') and old.get('vacancy_id') and j['vacancy_id']!=old['vacancy_id'] and gap>=30)
    return not proven_repost
