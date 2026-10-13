import re
from datetime import date
from pathlib import Path
from docx import Document
from docx.shared import Inches,Pt

def generate(j,p,root,today):
    folder=root/'outputs'/'letters'/today; folder.mkdir(parents=True,exist_ok=True)
    stem=re.sub(r'[^A-Za-z0-9]+','_',j['employer']+'_'+j['title']).strip('_')+'_'+j['vacancy_id']+'_CoverLetter'
    venue=j['employer'].split(' (')[0]
    exp=p['experience']
    hotel=[e for e in exp if any(w in e['role'].lower() for w in ('minibar','housekeep','hotel'))]
    retail=[e for e in exp if 'retail' in e['role'].lower()]
    evidence=' '.join(f"In my role as {e['role']} at {e['employer']}, I {', '.join(e['duties'][:-1])} and {e['duties'][-1]}." if len(e['duties'])>1 else f"At {e['employer']}, I {e['duties'][0]}." for e in hotel[:2])
    retail_evidence=' '.join(f"At {e['employer']}, I {', '.join(e['duties'][:-1])} and {e['duties'][-1]}." for e in retail[:1])
    desc=j['description'].lower()
    attraction = 'the welcoming neighbourhood atmosphere' if any(w in desc for w in ('local','lawn','home')) else 'the lively atmosphere and live music' if 'music' in desc else 'the energy of your waterfront venue' if 'viaduct' in j['location'].lower() else 'the focus on friendly guest experiences'
    paras=[date.fromisoformat(today).strftime('%d %B %Y'),venue,p['style']['greeting']+',',f"Re: {j['title']}",f"Please accept my application for the {j['title']} position at {venue}. I am a reliable, personable worker with experience in hospitality, retail and customer service, and I would welcome the opportunity to build on this in your front-of-house team.",evidence,f"I am drawn to {attraction} at {venue}. Your focus on welcoming customers, taking orders and supporting a busy team appeals to me. {retail_evidence} I would bring that customer focus and willingness to learn while developing the table-service skills needed for this role.","I work well with others, stay organised and take pride in presenting and acting professionally. I would appreciate the chance to discuss the role and your roster requirements.","Thank you for considering my application.",p['style']['closing']+',',p['name']]
    md=folder/(stem+'.md'); docx=folder/(stem+'.docx')
    md.write_text('\n\n'.join(paras)+'\n',encoding='utf-8')
    d=Document(); section=d.sections[0]; section.page_height=Inches(11.7); section.page_width=Inches(8.3)
    section.top_margin=section.bottom_margin=Inches(.75)
    normal=d.styles['Normal']; normal.font.name='Calibri'; normal.font.size=Pt(11); normal.paragraph_format.space_after=Pt(8)
    for text in paras: d.add_paragraph(text)
    d.core_properties.author=p['name']; d.save(docx)
    return str(md.relative_to(root)),str(docx.relative_to(root))
