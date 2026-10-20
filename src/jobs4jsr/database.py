import json, sqlite3
STATUSES=('New','Reviewed','Applied','Interview','Rejected','Closed')

def connect(path):
    path.parent.mkdir(parents=True,exist_ok=True)
    c=sqlite3.connect(path,timeout=30)
    c.execute('PRAGMA journal_mode=WAL')
    c.executescript("""CREATE TABLE IF NOT EXISTS jobs(id INTEGER PRIMARY KEY, url TEXT UNIQUE, status TEXT NOT NULL, payload TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS runs(id TEXT PRIMARY KEY, started TEXT, completed TEXT, diagnostics TEXT);
    CREATE TABLE IF NOT EXISTS status_history(id INTEGER PRIMARY KEY,job_id INTEGER,changed TEXT DEFAULT CURRENT_TIMESTAMP,status TEXT);
    CREATE TABLE IF NOT EXISTS source_checks(run_id TEXT NOT NULL, source TEXT NOT NULL, checked_at TEXT NOT NULL,
      last_successful_check TEXT, payload TEXT NOT NULL, PRIMARY KEY(run_id,source));
    CREATE TABLE IF NOT EXISTS metadata(key TEXT PRIMARY KEY,value TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS vacancy_events(id INTEGER PRIMARY KEY,job_id INTEGER,run_id TEXT,kind TEXT,changed TEXT,payload TEXT);
    CREATE TABLE IF NOT EXISTS update_checkpoints(run_id TEXT PRIMARY KEY, summary TEXT NOT NULL, published INTEGER NOT NULL DEFAULT 0);
    CREATE TABLE IF NOT EXISTS sync_runs(id INTEGER PRIMARY KEY,attempted TEXT,status TEXT,error TEXT);
    """)
    return c

def save_source_checks(c, run_id, checks):
    for check in checks:
        prior = c.execute('SELECT MAX(last_successful_check) FROM source_checks WHERE source=?',
                          (check['source'],)).fetchone()[0]
        if not check.get('last_successful_check'):
            check['last_successful_check'] = prior
        c.execute('''INSERT INTO source_checks VALUES(?,?,?,?,?)
            ON CONFLICT(run_id,source) DO UPDATE SET checked_at=excluded.checked_at,
            last_successful_check=excluded.last_successful_check,payload=excluded.payload''',
                  (run_id, check['source'], check['checked_at'], check['last_successful_check'], json.dumps(check)))

def source_checks(c, run_id=None):
    query = 'SELECT payload FROM source_checks'
    params = ()
    if run_id:
        query += ' WHERE run_id=?'; params = (run_id,)
    return [json.loads(row[0]) for row in c.execute(query, params)]

def jobs(c):
    return [dict(json.loads(p),id=i,status=s) for i,s,p in c.execute('SELECT id,status,payload FROM jobs')]

def add(c,j):
    cur=c.execute('INSERT INTO jobs(url,status,payload) VALUES(?,?,?)',(j['url'],'New',json.dumps(j)))
    return cur.lastrowid

def status(c,ident,value):
    if value not in STATUSES: raise ValueError('Invalid status')
    if c.execute('UPDATE jobs SET status=? WHERE id=?',(value,ident)).rowcount!=1: raise ValueError('Unknown job ID')
    c.execute('INSERT INTO status_history(job_id,status) VALUES(?,?)',(ident,value)); c.commit()
