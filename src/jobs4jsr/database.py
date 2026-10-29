import json, sqlite3
from datetime import datetime, timedelta, timezone
STATUSES=('New','Reviewed','Applied','Interview','Rejected','Closed')

# A claimed digest is protected for this long. It bounds how long a crashed or
# hung run can block the evening task, and it is the window in which a retry is
# guaranteed not to send a second copy.
LEASE_SECONDS=900

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
    CREATE TABLE IF NOT EXISTS board_leads(board TEXT NOT NULL, advert_id TEXT NOT NULL, url TEXT NOT NULL,
      first_seen TEXT NOT NULL, first_seen_run TEXT NOT NULL, last_seen TEXT NOT NULL, payload TEXT NOT NULL,
      PRIMARY KEY(board,advert_id));
    CREATE TABLE IF NOT EXISTS digest_sends(day TEXT PRIMARY KEY, sent TEXT NOT NULL,
      job_count INTEGER NOT NULL DEFAULT 0, lead_count INTEGER NOT NULL DEFAULT 0,
      state TEXT NOT NULL DEFAULT 'sent', owner TEXT, lease_until TEXT,
      attempts INTEGER NOT NULL DEFAULT 1, error TEXT);
    CREATE INDEX IF NOT EXISTS board_leads_last_seen ON board_leads(last_seen);
    """)
    _upgrade_digest(c)
    return c

def _upgrade_digest(c):
    """Additive migration: an existing database keeps its sent history."""
    columns={row[1] for row in c.execute('PRAGMA table_info(digest_sends)')}
    for name,ddl in (('state',"TEXT NOT NULL DEFAULT 'sent'"),('owner','TEXT'),('lease_until','TEXT'),
                     ('attempts','INTEGER NOT NULL DEFAULT 1'),('error','TEXT')):
        if name not in columns:
            c.execute('ALTER TABLE digest_sends ADD COLUMN '+name+' '+ddl)
    c.execute('CREATE INDEX IF NOT EXISTS board_leads_last_seen ON board_leads(last_seen)')
    c.commit()

def save_leads(c, leads, run_id, now):
    """Additive lead store. Returns only the leads seen for the first time.

    A card without an advert ID cannot be opened or deduplicated, so it is never
    stored; repeated cards in the same run are stored once.
    """
    new, seen = [], set()
    for lead in leads or []:
        key = (lead.get('board'), lead.get('advert_id'))
        if not key[1] or key in seen:
            continue
        seen.add(key)
        row = c.execute('SELECT 1 FROM board_leads WHERE board=? AND advert_id=?', key).fetchone()
        payload = json.dumps(lead)
        if row:
            c.execute('UPDATE board_leads SET last_seen=?,payload=? WHERE board=? AND advert_id=?',
                      (now, payload, lead['board'], lead['advert_id']))
            continue
        c.execute('INSERT INTO board_leads(board,advert_id,url,first_seen,first_seen_run,last_seen,payload)'
                  ' VALUES(?,?,?,?,?,?,?)',
                  (lead['board'], lead['advert_id'], lead['url'], now[:10], run_id, now, payload))
        new.append(lead)
    return new

def digest_sent(c, day):
    """The delivery record for a day, if the digest was actually sent."""
    return c.execute("SELECT day,sent,job_count,lead_count FROM digest_sends"
                     " WHERE day=? AND state='sent'", (day,)).fetchone()

def digest_attempts(c, day):
    row = c.execute('SELECT attempts FROM digest_sends WHERE day=?', (day,)).fetchone()
    return row[0] if row else 0

def _moment(value):
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)

def claim_digest(c, day, owner, now=None, lease_seconds=LEASE_SECONDS):
    """Atomically claim the day's digest.

    Returns 'claimed' when this process owns the send, 'sent' when the day is
    already delivered and 'busy' when another live claim holds the lease. The
    claim is durable, so it survives a restart and is visible to the other
    process; BEGIN IMMEDIATE serialises the check and the write.
    """
    moment = now or datetime.now(timezone.utc)
    expiry = (moment + timedelta(seconds=lease_seconds)).isoformat()
    try:
        c.execute('BEGIN IMMEDIATE')
    except sqlite3.OperationalError:
        return 'busy'
    try:
        row = c.execute('SELECT state,lease_until FROM digest_sends WHERE day=?', (day,)).fetchone()
        if row:
            state, lease = row
            if state == 'sent':
                c.rollback()
                return 'sent'
            if state == 'claimed':
                held = _moment(lease)
                if held and held > moment:
                    c.rollback()
                    return 'busy'
            c.execute("UPDATE digest_sends SET state='claimed',owner=?,lease_until=?,"
                      "attempts=attempts+1,error=NULL WHERE day=?", (owner, expiry, day))
        else:
            c.execute("INSERT INTO digest_sends(day,sent,job_count,lead_count,state,owner,lease_until,attempts)"
                      " VALUES(?,?,0,0,'claimed',?,?,1)", (day, '', owner, expiry))
        c.commit()
        return 'claimed'
    except Exception:
        c.rollback()
        raise

def mark_digest_sent(c, day, owner, sent, jobs, leads):
    """Record delivery. Only the owning claim may do this."""
    changed = c.execute("UPDATE digest_sends SET state='sent',sent=?,job_count=?,lead_count=?,"
                        "lease_until=NULL,error=NULL WHERE day=? AND owner=? AND state='claimed'",
                        (sent, jobs, leads, day, owner)).rowcount
    c.commit()
    return changed == 1

def fail_digest(c, day, owner, error):
    """Release a claim after a failed send so the next run may retry at once."""
    changed = c.execute("UPDATE digest_sends SET state='failed',error=?,lease_until=NULL"
                        " WHERE day=? AND owner=? AND state='claimed'", (error, day, owner)).rowcount
    c.commit()
    return changed == 1

def skip_digest(c, day, sent):
    """Record that a day had nothing to send, without overwriting real history."""
    c.execute("INSERT OR IGNORE INTO digest_sends(day,sent,job_count,lead_count,state,attempts)"
              " VALUES(?,?,0,0,'skipped',0)", (day, sent))
    c.commit()

def record_digest_day(c, day, state, sent, jobs, leads):
    """Upsert a day covered by a catch-up digest."""
    c.execute("INSERT INTO digest_sends(day,sent,job_count,lead_count,state,attempts) VALUES(?,?,?,?,?,1)"
              " ON CONFLICT(day) DO UPDATE SET state=excluded.state,sent=excluded.sent,"
              "job_count=excluded.job_count,lead_count=excluded.lead_count,error=NULL",
              (day, sent, jobs, leads, state))
    c.commit()

def digest_status(c, limit=20):
    """Recent digest outcomes for the operational log and status command."""
    return [{'day': day, 'state': state, 'attempts': attempts, 'jobs': jobs, 'leads': leads,
             'sent': sent, 'error': error}
            for day, state, attempts, jobs, leads, sent, error in c.execute(
                'SELECT day,state,attempts,job_count,lead_count,sent,error FROM digest_sends'
                ' ORDER BY day DESC LIMIT ?', (limit,))]

def leads(c, run_id=None, since=None):
    """Stored leads. `since` keeps a current view; history is never deleted."""
    query = 'SELECT payload,first_seen,first_seen_run,last_seen FROM board_leads'
    clauses, params = [], []
    if run_id:
        clauses.append('first_seen_run=?'); params.append(run_id)
    if since:
        clauses.append('substr(last_seen,1,10)>=?'); params.append(since)
    if clauses:
        query += ' WHERE ' + ' AND '.join(clauses)
    return [dict(json.loads(payload), first_seen=seen, first_seen_run=run, last_seen=last_seen)
            for payload, seen, run, last_seen in c.execute(query + ' ORDER BY board,advert_id', params)]

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
