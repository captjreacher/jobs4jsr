import html,json,re,time,urllib.robotparser,xml.etree.ElementTree as ET
from datetime import date
import requests
from .scoring import distance

AGENT='Jobs4JSR/0.1 (local personal vacancy research)'

def plain(value):
    return re.sub(r'\s+', ' ', html.unescape(re.sub('<[^>]+>',' ',html.unescape(value)))).strip()

class Client:
    def __init__(self,delay=1): self.session=requests.Session(); self.rules={}; self.delay=delay
    def get(self,url):
        from urllib.parse import urlsplit
        u=urlsplit(url); origin=u.scheme+'://'+u.netloc
        if origin not in self.rules:
            r=self.session.get(origin+'/robots.txt',timeout=25,headers={'User-Agent':AGENT})
            if r.status_code not in (200,404): raise RuntimeError('Robots unavailable: '+origin)
            rp=urllib.robotparser.RobotFileParser(); rp.parse(r.text.splitlines() if r.status_code==200 else [])
            self.rules[origin]=rp
        if not self.rules[origin].can_fetch(AGENT,url): raise RuntimeError('Robots disallows '+url)
        time.sleep(max(self.delay,self.rules[origin].crawl_delay(AGENT) or 0))
        r=self.session.get(url,timeout=25,headers={'User-Agent':AGENT}); r.raise_for_status()
        if urlsplit(r.url).netloc!=u.netloc: raise RuntimeError('Cross-domain redirect; review required')
        r.encoding='utf-8'
        return r.text

def discover(settings,today):
    client=Client(settings.get('request_delay',1)); result=[]; diagnostics=[]
    for source in settings['sources']:
        try:
            sitemap=ET.fromstring(client.get(source['sitemap']))
            urls=[e.text for e in sitemap.iter() if e.tag.endswith('loc') and e.text and '/jobs/' in e.text and 'front-of-house' in e.text]
            diagnostics.append(f"{source['name']}: {len(urls)} specific FOH URLs found")
            for url in urls:
                try:
                    page=client.get(url)
                    scripts=re.findall(r'<script[^>]*application/ld\+json[^>]*>(.*?)</script>',page,re.S|re.I)
                    records=[json.loads(x) for x in scripts]
                    item=next((x for x in records if isinstance(x,dict) and x.get('@type')=='JobPosting'),None)
                    if not item: raise ValueError('No active JobPosting structured data')
                    if item.get('validThrough') and item['validThrough'][:10]<today: continue
                    if 'loading application form' not in page.lower() and '/apply' not in page.lower(): raise ValueError('No application action found')
                    location=item['jobLocation']; location=location[0] if isinstance(location,list) else location
                    address=location['address']; venue=address.get('streetAddress','')
                    geo=settings['venues'].get(venue)
                    if not geo:
                        diagnostics.append('Skipped unverified location: '+venue); continue
                    description=plain(item['description']).strip()
                    if re.search(r'(position (?:is|has been) filled|no longer accepting applications|vacancy closed)',plain(page),re.I): continue
                    visible_type=re.search(r'Employment Type\s+(Casual|Part-time(?:, Full-time)?|Full-time)',plain(page),re.I)
                    job_type=visible_type.group(1) if visible_type else item.get('employmentType','Unknown')
                    posted=item.get('datePosted','')[:10]
                    result.append(dict(vacancy_id=str(item.get('identifier',{}).get('value',url)),source=source['name'],url=url,employer=geo.get('employer',venue)+' (Star Group)',title=item['title'],location=geo['location'],coordinates=geo['coordinates'],distance=round(distance(settings['centre'],geo['coordinates']),2),coordinate_basis=geo['basis'],job_type=job_type,structured_job_type=item.get('employmentType','Unknown'),posted=posted or None,recent=bool(posted and 0<=(date.fromisoformat(today)-date.fromisoformat(posted)).days<=30),description=description,salary=None,hours=None,active_evidence='Live employer JobPosting and application action',uncertainties=['Confirm availability, work eligibility and shift requirements; table service training needed', 'Visible employment type takes precedence over conflicting structured data']))
                except Exception as e: diagnostics.append('Vacancy verification failed '+url+': '+str(e))
        except Exception as e: diagnostics.append('SOURCE FAILED '+source['name']+': '+str(e))
    diagnostics.append('SEEK, Trade Me, Indeed and recruiter pages: supplementary manual research only; no unauthorised scraping or scheduled access configured.')
    return result,diagnostics
