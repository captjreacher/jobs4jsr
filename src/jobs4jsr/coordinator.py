"""Single canonical-root execution gate and durable deferred scheduled slots."""
import contextlib
import json
import os
import sqlite3
import threading
import time

class Busy(RuntimeError):
    pass

_local = threading.local()

@contextlib.contextmanager
def execution_lock(root):
    path = (root / 'data/private/execution.lock').resolve()
    held = getattr(_local, 'held', set())
    if path in held:
        yield
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    handle = open(path, 'a+b')
    handle.seek(0); handle.write(b'0'); handle.flush(); handle.seek(0)
    try:
        try:
            if os.name == 'nt':
                import msvcrt
                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            raise Busy('Another discovery/publication is active') from None
        _local.held = held | {path}
        try:
            yield
        finally:
            _local.held = held
            handle.seek(0)
            if os.name == 'nt':
                import msvcrt
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
    finally:
        handle.close()

@contextlib.contextmanager
def control(root):
    path = root / 'data/private/runner-control.sqlite3'
    path.parent.mkdir(parents=True, exist_ok=True)
    c = sqlite3.connect(path, timeout=10)
    c.execute('create table if not exists deferred_slots(id text primary key, state text not null, attempts integer not null default 0, available real not null default 0, error text)')
    try:
        with c: yield c
    finally: c.close()

def defer(root, slot):
    with control(root) as c:
        c.execute("insert or ignore into deferred_slots(id,state) values(?,'queued')", (slot,))

def next_slot(root):
    with control(root) as c:
        row = c.execute("select id from deferred_slots where state in ('queued','running') and available<=? order by id limit 1", (time.time(),)).fetchone()
        return row[0] if row else None

def finish_slot(root, slot, success):
    with control(root) as c:
        if success:
            c.execute('delete from deferred_slots where id=?', (slot,))
        else:
            c.execute("update deferred_slots set state=case when attempts>=3 then 'failed' else 'queued' end,available=?,error='scheduled_run_failed' where id=?", (time.time()+60,slot))

@contextlib.contextmanager
def command(root, name, slot=None):
    if slot: defer(root, slot)
    with contextlib.ExitStack() as stack:
        try:
            stack.enter_context(execution_lock(root))
        except Busy:
            if slot:
                print('Scheduled slot deferred durably:',slot)
                yield False
                return
            raise
        if slot:
            with control(root) as c:
                c.execute("update deferred_slots set attempts=attempts+1,state=case when attempts>=3 then 'failed' else 'running' end,error=case when attempts>=3 then 'attempts_exhausted' else null end where id=?",(slot,))
                state=c.execute('select state from deferred_slots where id=?',(slot,)).fetchone()[0]
            if state == 'failed':
                print('Scheduled slot retained for operator recovery:',slot)
                yield False
                return
        try:
            yield True
        except BaseException:
            if slot: finish_slot(root,slot,False)
            raise
        else:
            if slot: finish_slot(root,slot,True)
