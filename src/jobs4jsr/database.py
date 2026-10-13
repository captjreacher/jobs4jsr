import json, sqlite3
STATUSES=('New','Reviewed','Applied','Interview','Rejected','Closed')

def connect(path):
    path.parent.mkdir(parents=True,exist_ok=True)
    c=sqlite3.connect(path,timeout=30)
    c.execute('PRAGMA journal_mode=WAL')
    c.executescript("""CREATE TABLE IF NOT EXISTS jobs(id INTEGER PRIMARY KEY, url TEXT UNIQUE, status TEXT NOT NULL, payload TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS runs(id TEXT PRIMARY KEY, started TEXT, completed TEXT, diagnostics TEXT);
    CREATE TABLE IF NOT EXISTS status_history(id INTEGER PRIMARY KEY,job_id INTEGER,changed TEXT DEFAULT CURRENT_TIMESTAMP,status TEXT);
    """)
    return c

def jobs(c):
    return [dict(json.loads(p),id=i,status=s) for i,s,p in c.execute('SELECT id,status,payload FROM jobs')]

def add(c,j):
    cur=c.execute('INSERT INTO jobs(url,status,payload) VALUES(?,?,?)',(j['url'],'New',json.dumps(j)))
    return cur.lastrowid

def status(c,ident,value):
    if value not in STATUSES: raise ValueError('Invalid status')
    if c.execute('UPDATE jobs SET status=? WHERE id=?',(value,ident)).rowcount!=1: raise ValueError('Unknown job ID')
    c.execute('INSERT INTO status_history(job_id,status) VALUES(?,?)',(ident,value)); c.commit()
