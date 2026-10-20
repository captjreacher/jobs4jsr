"""Outbound-only single-PC poller. No sourcing engine or inbound listener."""
import argparse
import json
import logging
from logging.handlers import RotatingFileHandler
import os
import threading
import time
from pathlib import Path
import requests
from . import cli, coordinator, database, sync

LOG = logging.getLogger(__name__)

class API:
    def __init__(self, env=None, session=None):
        env = env or os.environ
        self.base = env['JOBS4JSR_SUPABASE_URL'].rstrip('/')
        if not self.base.startswith('https://'): raise ValueError('HTTPS required')
        self.email, self.password = env['JOBS4JSR_SYNC_EMAIL'], env['JOBS4JSR_SYNC_PASSWORD']
        self.session = session or requests.Session()
        self.session.headers.update(apikey=env['JOBS4JSR_PUBLISHABLE_KEY'])
        self.login()

    def login(self):
        r = self.session.post(self.base+'/auth/v1/token?grant_type=password',json={'email':self.email,'password':self.password},timeout=30)
        r.raise_for_status()
        self.session.headers['Authorization'] = 'Bearer '+r.json()['access_token']

    def call(self, path, payload=None, method='POST'):
        for attempt in range(2):
            r = self.session.request(method,self.base+path,json=payload,timeout=30)
            if r.status_code == 401 and attempt == 0:
                self.login(); continue
            r.raise_for_status()
            return r.json()
        raise RuntimeError('Authentication unavailable')

    def rpc(self, name, **args):
        return self.call('/rest/v1/rpc/jobs4jsr_'+name,args)

    def request(self, ident):
        # Select only safe columns; claim tokens never have direct SELECT grants.
        rows = self.call('/rest/v1/jobs4jsr_update_requests?id=eq.'+ident+'&select=id,state,summary',method='GET')
        return rows[0] if rows else None

class Claim:
    def __init__(self, api, row):
        self.api, self.id, self.token = api, row['id'], row['claim_token']
        self.finished = False

    def heartbeat(self):
        return self.api.rpc('runner_heartbeat',p_request=self.id,p_token=self.token,p_busy=True)

    def publish(self, payload):
        result = self.api.rpc('publish_update',p_request=self.id,p_token=self.token,p_payload=payload)
        self.finished = True
        return result

    def terminal(self):
        row = self.api.request(self.id)
        return bool(row and row['state'] in ('completed','failed') and row.get('summary') is not None)

class Guard:
    """Heartbeat thread also enforces a hard bound on the whole runner process.

    Pipeline runs in this process (no orphanable child). os._exit stops all its
    threads, releases the OS lock and rolls back uncommitted SQLite work. The
    supervisor restarts it; cloud lease and local checkpoints drive recovery.
    """
    def __init__(self, heartbeat, terminal=lambda:False, timeout=1200, abort=None):
        self.heartbeat, self.terminal, self.timeout = heartbeat, terminal, timeout
        self.abort = abort or os._exit
        self.stopped = threading.Event()
        self.started = self.last_ok = time.monotonic()

    def check(self):
        now = time.monotonic()
        if now-self.started >= self.timeout:
            self.abort(75); return
        try:
            self.heartbeat(); self.last_ok = time.monotonic()
        except Exception:
            try:
                if self.terminal(): self.stopped.set(); return
            except Exception:
                pass
            if time.monotonic()-self.last_ok >= 90:
                self.abort(75)

    def run(self):
        while not self.stopped.wait(20): self.check()

    def watch(self):
        # Independent of HTTP: a blocked heartbeat cannot disable the watchdog.
        while not self.stopped.wait(1):
            now = time.monotonic()
            if now-self.started >= self.timeout or now-self.last_ok >= 90:
                self.stopped.set(); self.abort(75); return

    def __enter__(self):
        self.watcher = threading.Thread(target=self.watch,daemon=True); self.watcher.start()
        try:
            self.heartbeat()  # fail closed before starting discovery
            self.last_ok = time.monotonic()
        except BaseException:
            self.stopped.set(); self.watcher.join(timeout=2); raise
        self.thread = threading.Thread(target=self.run,daemon=True); self.thread.start()
        return self

    def __exit__(self,*args):
        self.stopped.set(); self.watcher.join(timeout=2); self.thread.join(timeout=35)


def reconcile_publications(root, api):
    c = database.connect(root/'data/private/jobs.sqlite3')
    try:
        for run_id, in c.execute("select run_id from update_checkpoints where published=0 and run_id like 'manual-update-%'").fetchall():
            row = api.request(run_id.removeprefix('manual-update-'))
            if row and row['state'] in ('completed','failed') and row.get('summary') is not None:
                c.execute('update update_checkpoints set published=1 where run_id=?',(run_id,))
        c.commit()
    finally: c.close()

def tick(root, api):
    api.rpc('runner_heartbeat',p_request=None,p_token=None,p_busy=False)
    try:
        with coordinator.execution_lock(root):
            reconcile_publications(root,api)
            slot = coordinator.next_slot(root)
            if slot:
                # Same scheduled CLI, same original slot, before queued manual work.
                with Guard(lambda: api.rpc('runner_heartbeat',p_request=None,p_token=None,p_busy=True)):
                    cli.main(['--root',str(root),'scheduled','--slot',slot])
                return
            row = api.rpc('claim_update')
            if not row: return
            claim = Claim(api,row)
            LOG.info('Claimed update %s, attempt %s',claim.id,row.get('attempt'))
            try:
                with Guard(claim.heartbeat,claim.terminal):
                    cli.main(['--root',str(root),'search','--run-id','update-'+claim.id],update_control=claim)
            except BaseException as exc:
                # Partial-source exit 2 can follow successful atomic publication.
                if isinstance(exc, (KeyboardInterrupt,GeneratorExit)): raise
                if not claim.finished and not claim.terminal():
                    api.rpc('fail_update',p_request=claim.id,p_token=claim.token,
                            p_code='publication_failed' if isinstance(exc,RuntimeError) else 'discovery_failed')
                if not claim.finished: LOG.warning('Request attempt ended (%s)',type(exc).__name__)
    except coordinator.Busy:
        api.rpc('runner_heartbeat',p_request=None,p_token=None,p_busy=True)

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',type=Path,required=True)
    parser.add_argument('--once',action='store_true',help='Poll once; may execute real queued discovery; use only after release approval')
    args=parser.parse_args(); root=args.root.resolve(); sync.load_env(root)
    if os.environ.get('JOBS4JSR_MANUAL_UPDATES_ENABLED') != 'true':
        raise RuntimeError('Poller disabled; enable only after release approval')
    logs=root/'outputs/logs'; logs.mkdir(parents=True,exist_ok=True)
    logging.basicConfig(level=logging.INFO,format='%(asctime)s %(levelname)s %(message)s',
        handlers=[RotatingFileHandler(logs/'update-poller.log',maxBytes=5_000_000,backupCount=3,encoding='utf-8')])
    api=None
    while True:
        try:
            if api is None: api=API()
            tick(root,api)
        except Exception as exc:
            # Do not log HTTP bodies, tokens, credentials or local candidate data.
            LOG.warning('Runner unavailable (%s)',type(exc).__name__); api=None
        if args.once: return
        time.sleep(30)

if __name__=='__main__': main()
