import math, re

def target_role(title):
    text = re.sub(r'\s+', ' ', title.lower().replace('-', ' '))
    if re.search(r'\b(engineer|developer|technician|network|database|software|sales)\b', text):
        return False
    return bool(re.search(r'\b(waitress|waiter|waitstaff|wait staff|waiting staff|restaurant server|server|front of house|foh|'
                          r'food (?:and|&) beverage attendant|f&b attendant|host|hostess|'
                          r'hospitality (?:team member|attendant|assistant)|guest services? agent|'
                          r'guest service|cafe (?:all rounder|assistant|team member)|café assistant|floor staff)\b', text))

def distance(a,b):
    la,lo,lb,lob=map(math.radians,(*a,*b))
    h=math.sin((lb-la)/2)**2+math.cos(la)*math.cos(lb)*math.sin((lob-lo)/2)**2
    return 6371.0088*2*math.asin(min(1,math.sqrt(h)))

def score(job,profile):
    title=job['title'].lower(); text=job['description'].lower()
    if not target_role(title): return None
    if any(x in title for x in ['manager','senior','supervisor','leader','chef']): return None
    if 'barista' in title and not profile.get('barista'): return None
    if re.search(r'(must|required|essential).{0,60}(barista|lcq|manager.s certificate)',text): return None
    if re.search(r'(minimum|at least)\s+[2-9]\s+years.{0,40}(wait|table|barista)',text): return None
    if 'previous experience in similar role within food & beverage' in text and not profile.get('table_service'): return None
    if not profile.get('table_service') and re.search(r'(experienced|experience.{0,15}(essential|required))\s+(waiter|waitress|waitstaff|server)', title + ' ' + text): return None
    if not profile.get('table_service') and re.search(r'(at least|minimum)\s+\d+\s+year.{0,70}(luxury|5.star|table service|waiting)', text): return None
    if job['distance']>10: return None
    service=15 if 'customer service' in text else 5
    team=10 if any(x in text for x in ['team','communication']) else 0
    learning=15 if any(x in text for x in ['training','train for skill','not necessary','learn']) else 5
    geography=15 if job['distance']<=2 else 12 if job['distance']<=5 else 8
    skills=20 if 'customer service' in profile['skills'] else 0
    # Target role 20, transferable skills 20, service 15, team 10, learnability 15, geography 15, freshness 5.
    freshness=5 if job.get('recent') else 0
    total=20+skills+service+team+learning+geography+freshness
    return min(total - (10 if not profile.get('table_service') else 0),100), 'Hotel guest support and retail customer service transfer to this role; '+('training is offered.' if learning==15 else 'service training should be discussed.')
