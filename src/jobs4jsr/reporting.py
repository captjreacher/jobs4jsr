import html,os
from pathlib import Path
HEADERS=['ID','Date found','Employer','Position','Location','Distance','Job type','Match','Why it suits Jess','Job link','Suggested letter','Status','Date posted','Pay','Hours','Uncertainties','Last verified']

def report(root,today,rows,diagnostics,run_id):
    folder=root/'outputs'/'reports'/today; folder.mkdir(parents=True,exist_ok=True)
    rows=sorted(rows,key=lambda j:(-j['match'], -(int((j.get('posted') or '0000-00-00').replace('-','')))))
    def cells(j):
        return [j['id'],j['found'],j['employer'],j['title'],j['location'],f"{j['distance']:.1f} km approx",j['job_type'],str(j['match'])+'/100',j['why'],j['url'],j['letter_docx'],j['status'],j.get('posted') or 'Unknown',j.get('salary') or 'Unknown',j.get('hours') or 'Unknown','; '.join(j.get('uncertainties',[])),j.get('last_verified','Unknown')]
    def relative(path,base): return Path(os.path.relpath(root/path,base)).as_posix()
    intro=f'Jobs4JSR — {today}\nRun: {run_id}. {len(rows)} new suitable vacancies. Letters require Jess’s review. Distances are straight-line estimates. Availability and work rights need confirmation.'
    def make_html(base):
        trs=[]
        for j in rows:
            values=cells(j); td=[]
            for n,v in enumerate(values):
                if n==9: value='<a href="'+html.escape(str(v),quote=True)+'">View advertisement</a>'
                elif n==10: value='<a href="'+html.escape(relative(v,base),quote=True)+'">Word letter</a> · <a href="'+html.escape(relative(j['letter_md'],base),quote=True)+'">Read letter</a>'
                else: value=html.escape(str(v))
                td.append('<td>'+value+'</td>')
            trs.append('<tr>'+''.join(td)+'</tr>')
        return '<!doctype html><html lang="en-NZ"><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>Jess’s job opportunities</title><style>body{font:16px system-ui;color:#17313b;background:#f4f7f9;margin:24px}main{max-width:1500px;margin:auto}h1{font-size:28px}.scroll{overflow:auto}table{border-collapse:collapse;background:white}td,th{padding:12px;text-align:left;border-bottom:1px solid #ddd;min-width:110px}th{background:#17313b;color:white}a{color:#006a82}li{margin:8px 0}</style><main><h1>Jess’s job opportunities</h1><p>'+html.escape(intro)+'</p><div class="scroll"><table><thead><tr>'+''.join('<th scope="col">'+x+'</th>' for x in HEADERS)+'</tr></thead><tbody>'+''.join(trs)+'</tbody></table></div><h2>Search notes and limitations</h2><ul>'+''.join('<li>'+html.escape(x)+'</li>' for x in diagnostics)+'</ul></main></html>'
    dated=folder/'report.html'; dated.write_text(make_html(folder),encoding='utf-8')
    (folder/(run_id+'.html')).write_text(make_html(folder),encoding='utf-8')
    latest=folder.parent/'latest.html'; latest.write_text(make_html(folder.parent),encoding='utf-8')
    md=['# '+intro,'','| '+' | '.join(HEADERS)+' |','| '+' | '.join(['---']*len(HEADERS))+' |']
    for j in rows:
        v=[str(x).replace('|','\\|').replace('\n',' ') for x in cells(j)]
        v[9]='[Advertisement]('+j['url']+')'; v[10]='[Word letter]('+relative(j['letter_docx'],folder)+')'
        md.append('| '+' | '.join(v)+' |')
    md+=['','## Search notes']+['- '+x for x in diagnostics]
    (folder/'report.md').write_text('\n'.join(md),encoding='utf-8')
    (folder/(run_id+'.md')).write_text('\n'.join(md),encoding='utf-8')
    return latest
