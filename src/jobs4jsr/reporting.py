import html,os
from pathlib import Path
HEADERS=['ID','Date found','Employer','Position','Location','Distance','Job type','Match','Why it suits Jess','Job link','Suggested letter','Status','Date posted','Pay','Hours','Uncertainties','Last verified','Advert state','Recommendation']

LEAD_HEADERS=['Board','Position','Employer','Location','Pay','Posted','Listing link']

def report(root,today,rows,diagnostics,run_id,source_checks=None,leads=None):
    folder=root/'outputs'/'reports'/today; folder.mkdir(parents=True,exist_ok=True)
    rows=sorted(rows,key=lambda j:(-j['match'], -(int((j.get('posted') or '0000-00-00').replace('-','')))))
    def cells(j):
        return [j['id'],j['found'],j['employer'],j['title'],j['location'],f"{j['distance']:.1f} km approx",j['job_type'],str(j['match'])+'/100',j['why'],j['url'],j['letter_docx'],j['status'],j.get('posted') or 'Unknown',j.get('salary') or 'Unknown',j.get('hours') or 'Unknown','; '.join(j.get('uncertainties',[])),j.get('last_verified','Unknown'),j.get('vacancy_state','Unverified'), 'Top NEW opportunity' if j.get('recommended') else '']
    def relative(path,base): return Path(os.path.relpath(root/path,base)).as_posix()
    intro=f'Jobs4JSR — {today}\nRun: {run_id}. {len(rows)} suitable vacancies recorded for this view. Letters require Jess’s review. Distances are straight-line estimates. Availability and work rights need confirmation.'
    check_headers=['Source','State','Last successful check','Inspected','Verified','Qualified','Duplicates','Selected','Errors']
    check_values=[[c['source'],c['status'],c.get('last_successful_check') or 'Never',c['inspected'],c['verified'],c['qualified'],c['duplicates'],c['selected'],'; '.join(c['errors']) or 'None'] for c in source_checks or []]
    check_html='<h2>Source checks</h2><div class="scroll"><table><tr>'+''.join('<th>'+x+'</th>' for x in check_headers)+'</tr>'+''.join('<tr>'+''.join('<td>'+html.escape(str(x))+'</td>' for x in row)+'</tr>' for row in check_values)+'</table></div>' if check_values else ''
    lead_values=[[x.get('board') or '',x['title'],x.get('employer') or 'Not listed',x.get('location') or 'Not listed',x.get('pay') or 'Unknown',x.get('listed') or x.get('posted') or 'Unknown',x['url']] for x in sorted(leads or [],key=lambda x:(x.get('board') or '',x['title']))]
    lead_html='<h2>Unverified leads from other boards</h2><p>Only the public listing or search page was read; no advert page was fetched. Leads have no confirmed application action, so they carry no score, distance or letter. Open and check each one.</p><div class="scroll"><table><tr>'+''.join('<th>'+x+'</th>' for x in LEAD_HEADERS)+'</tr>'+''.join('<tr>'+''.join('<td>'+('<a href="'+html.escape(str(v),quote=True)+'">Open listing</a>' if n==6 else html.escape(str(v)))+'</td>' for n,v in enumerate(row))+'</tr>' for row in lead_values)+'</table></div>' if lead_values else ''
    def make_html(base):
        trs=[]
        for j in rows:
            values=cells(j); td=[]
            for n,v in enumerate(values):
                if n==9: value='<a href="'+html.escape(str(v),quote=True)+'">View advertisement</a>'
                elif n==10: value=('<a href="'+html.escape(relative(v,base),quote=True)+'">Word letter</a> · <a href="'+html.escape(relative(j['letter_md'],base),quote=True)+'">Read letter</a>') if v else 'Generate locally on request'
                else: value=html.escape(str(v))
                td.append('<td>'+value+'</td>')
            trs.append('<tr>'+''.join(td)+'</tr>')
        return '<!doctype html><html lang="en-NZ"><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>Jess’s job opportunities</title><style>body{font:16px system-ui;color:#17313b;background:#f4f7f9;margin:24px}main{max-width:1500px;margin:auto}h1{font-size:28px}.scroll{overflow:auto}table{border-collapse:collapse;background:white}td,th{padding:12px;text-align:left;border-bottom:1px solid #ddd;min-width:110px}th{background:#17313b;color:white}a{color:#006a82}li{margin:8px 0}</style><main><h1>Jess’s job opportunities</h1><p>'+html.escape(intro)+'</p><div class="scroll"><table><thead><tr>'+''.join('<th scope="col">'+x+'</th>' for x in HEADERS)+'</tr></thead><tbody>'+''.join(trs)+'</tbody></table></div>'+check_html+lead_html+'<h2>Search notes and limitations</h2><ul>'+''.join('<li>'+html.escape(x)+'</li>' for x in diagnostics)+'</ul></main></html>'
    dated=folder/'report.html'; dated.write_text(make_html(folder),encoding='utf-8')
    (folder/(run_id+'.html')).write_text(make_html(folder),encoding='utf-8')
    latest=folder.parent/'latest.html'; latest.write_text(make_html(folder.parent),encoding='utf-8')
    md=['# '+intro,'','| '+' | '.join(HEADERS)+' |','| '+' | '.join(['---']*len(HEADERS))+' |']
    for j in rows:
        v=[str(x).replace('|','\\|').replace('\n',' ') for x in cells(j)]
        v[9]='[Advertisement]('+j['url']+')'; v[10]='[Word letter]('+relative(j['letter_docx'],folder)+')' if j.get('letter_docx') else 'Generate locally on request'
        md.append('| '+' | '.join(v)+' |')
    if check_values:
        md+=['','## Source checks','','| '+' | '.join(check_headers)+' |','| '+' | '.join(['---']*len(check_headers))+' |']
        md+=['| '+' | '.join(str(x).replace('|','\\|').replace('\n',' ') for x in row)+' |' for row in check_values]
    if lead_values:
        md+=['','## Unverified leads from other boards','',
             'Only the public listing or search page was read; no advert page was fetched. Leads carry no score, distance or letter.',
             '','| '+' | '.join(LEAD_HEADERS)+' |','| '+' | '.join(['---']*len(LEAD_HEADERS))+' |']
        md+=['| '+' | '.join(('[Open listing]('+str(row[6])+')' if n==6 else str(v).replace('|','\\|').replace('\n',' ')) for n,v in enumerate(row))+' |' for row in lead_values]
    md+=['','## Search notes']+['- '+x for x in diagnostics]
    (folder/'report.md').write_text('\n'.join(md),encoding='utf-8')
    (folder/(run_id+'.md')).write_text('\n'.join(md),encoding='utf-8')
    return latest
