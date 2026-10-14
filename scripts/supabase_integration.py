"""Prepared real-API checks. Defaults to a plan; never creates users; membership negative tests must be denied.

Production execution requires separately supplied JWTs and explicit fixture approval.
No CVs, candidate profiles, application letters, passwords or admin keys are used.
"""
import argparse
import os
import uuid
from datetime import datetime, timezone
import requests

URL = 'https://qnvihygrnfgpmsznayje.supabase.co'
TABLES = ('members', 'jobs', 'decisions', 'runs', 'source_checks', 'sync_health')


def approved(args, env):
    if args.write_fixtures and env.get('JOBS4JSR_INTEGRATION_WRITE_APPROVAL') != 'APPROVED_FIRST_RELEASE_SYNTHETIC_TESTS':
        raise ValueError('Synthetic production writes require separate owner approval')
    if args.storage_fixtures and (not args.write_fixtures or env.get('JOBS4JSR_SYNTHETIC_STORAGE_APPROVAL') != 'APPROVED_SYNTHETIC_STORAGE_ONLY'):
        raise ValueError('Synthetic Storage tests require separate approval; no cover letters are uploaded')
    if env.get('JOBS4JSR_LETTER_UPLOAD_APPROVED', 'false') != 'false':
        raise ValueError('Generated-letter uploads must remain disabled')


class API:
    def __init__(self, key, session=None):
        self.key = key
        self.session = session or requests.Session()

    def call(self, path, token=None, method='GET', **kwargs):
        headers = {'apikey': self.key, 'Content-Type': 'application/json'}
        if token:
            headers['Authorization'] = 'Bearer ' + token
        headers.update(kwargs.pop('headers', {}))
        return self.session.request(method, URL + path, headers=headers, timeout=30, **kwargs)

    def rows(self, table, token, query='select=*'):
        r = self.call('/rest/v1/jobs4jsr_' + table + '?' + query, token)
        if r.status_code in (401, 403):
            return []
        if r.status_code != 200:
            raise AssertionError('Data API read failed; HTTP ' + str(r.status_code))
        return r.json()

    def write(self, table, token, row, conflict='id'):
        r = self.call('/rest/v1/jobs4jsr_' + table + '?on_conflict=' + conflict, token, 'POST',
                      json=row, headers={'Prefer': 'resolution=merge-duplicates,return=representation'})
        if r.status_code not in (200, 201):
            raise AssertionError('Fixture write failed; HTTP ' + str(r.status_code))
        return r.json()


def run(args, env, api=None):
    approved(args, env)
    required = ('JOBS4JSR_PUBLISHABLE_KEY', 'JOBS4JSR_OWNER_JWT', 'JOBS4JSR_PUBLISHER_JWT', 'JOBS4JSR_UNRELATED_JWT')
    if not all(env.get(k) for k in required):
        raise ValueError('Supply approved real identities through the private process environment')
    api = api or API(env[required[0]])
    tokens = {role: env[key] for role, key in zip(('owner', 'publisher', 'unrelated'), required[1:])}
    users = {}
    for role, token in tokens.items():
        r = api.call('/auth/v1/user', token)
        assert r.status_code == 200, 'Valid real JWT required for ' + role
        users[role] = r.json()['id']
    assert len(set(users.values())) == 3, 'Three distinct identities required'
    for table in TABLES:
        assert not api.rows(table, None), 'Anonymous data exposure: ' + table
        assert not api.rows(table, tokens['unrelated']), 'Unrelated-user exposure: ' + table
    owner_members = api.rows('members', tokens['owner'])
    publisher_members = api.rows('members', tokens['publisher'])
    assert owner_members == [{'user_id': users['owner'], 'owner_id': users['owner'], 'kind': 'reader'}]
    assert publisher_members == [{'user_id': users['publisher'], 'owner_id': users['owner'], 'kind': 'sync'}]
    print('PASS: real Auth identities, anonymous/unrelated denial and explicit memberships')
    if not args.write_fixtures:
        print('Fixture, Storage and refresh tests not run: write approval required')
        return
    assert not api.rows('jobs', tokens['owner']), 'Write tests require an empty first-release catalogue; stop if already populated'
    job = str(uuid.uuid4()); run_id = 'integration-' + job
    now = datetime.now(timezone.utc).isoformat()
    print('Synthetic fixture identifiers: job=' + job + ' run=' + run_id + ' timestamp=' + now)
    row = {'id': job, 'owner_id': users['owner'], 'vacancy': {'title': 'Synthetic preflight fixture', 'fixture': True}, 'letters': {}}
    for _ in range(2):
        api.write('jobs', tokens['publisher'], row)
    assert len(api.rows('jobs', tokens['owner'], 'select=*&id=eq.' + job)) == 1
    decision = {'job_id': job, 'owner_id': users['owner'], 'saved': False, 'dismissed': False, 'applied': False}
    api.write('decisions', tokens['owner'], decision, 'job_id')
    for field, value in [('saved', True), ('dismissed', True), ('applied', True), ('dismissed', False)]:
        r = api.call('/rest/v1/jobs4jsr_decisions?job_id=eq.' + job, tokens['owner'], 'PATCH',
                     json={field: value}, headers={'Prefer': 'return=representation'})
        assert r.status_code == 200 and r.json()[0][field] == value
    expected = api.rows('decisions', tokens['owner'], 'select=*&job_id=eq.' + job)
    api.write('jobs', tokens['publisher'], row)
    assert api.rows('decisions', tokens['owner'], 'select=*&job_id=eq.' + job) == expected
    for role in ('owner', 'publisher', 'unrelated'):
        r = api.call('/rest/v1/jobs4jsr_members', tokens[role], 'POST',
                     json={'user_id': users[role], 'owner_id': users['owner'], 'kind': 'sync'})
        assert r.status_code in (401, 403), 'Membership self-grant was not denied'
    r = api.call('/rest/v1/jobs4jsr_decisions', tokens['publisher'], 'POST', json=decision)
    assert r.status_code in (401, 403), 'Publisher decision write was not denied'
    assert not api.rows('decisions', tokens['publisher'])
    api.write('runs', tokens['publisher'], {'id': run_id, 'owner_id': users['owner'], 'started': now, 'completed': now, 'diagnostics': ['Synthetic fixture']})
    api.write('source_checks', tokens['publisher'], {'run_id': run_id, 'source': 'Synthetic fixture', 'owner_id': users['owner'], 'payload': {'checked_at': now, 'status': 'success'}}, 'run_id,source')
    prior_health = api.rows('sync_health', tokens['publisher'])
    api.write('sync_health', tokens['publisher'], {'owner_id': users['owner'], 'last_successful_sync': now}, 'owner_id')
    assert api.rows('source_checks', tokens['owner'], 'select=*&run_id=eq.' + run_id)
    assert api.rows('sync_health', tokens['owner'])
    if prior_health:
        api.write('sync_health', tokens['publisher'], prior_health[0], 'owner_id')
    print('PASS: decisions, publisher upsert/idempotency/isolation and discovery health')
    if args.storage_fixtures:
        key = users['owner'] + '/' + job + '/synthetic.md'
        path = '/storage/v1/object/jobs4jsr-letters/' + key
        r = api.call(path, tokens['publisher'], 'POST', data=b'Synthetic nonpersonal Storage permission fixture.', headers={'Content-Type': 'text/markdown'})
        assert r.status_code in (200, 201)
        download = '/storage/v1/object/authenticated/jobs4jsr-letters/' + key
        assert api.call(download, tokens['owner']).status_code == 200
        for token in (None, tokens['unrelated']):
            assert api.call(download, token).status_code in (400, 401, 403, 404)
        other = '/storage/v1/object/jobs4jsr-letters/' + users['unrelated'] + '/' + job + '/synthetic.md'
        assert api.call(other, tokens['publisher'], 'POST', data=b'Synthetic fixture.', headers={'Content-Type': 'text/markdown'}).status_code in (400, 401, 403)
        print('PASS: private synthetic Storage and cross-user denial')
    else:
        print('Storage tests not run: separate synthetic-upload approval required')
    expired = env.get('JOBS4JSR_EXPIRED_OWNER_JWT')
    refresh = env.get('JOBS4JSR_OWNER_REFRESH_TOKEN')
    if expired and refresh:
        assert api.call('/auth/v1/user', expired).status_code in (401, 403)
        r = api.call('/auth/v1/token?grant_type=refresh_token', method='POST', json={'refresh_token': refresh})
        assert r.status_code == 200
        fresh = r.json()['access_token']
        assert api.call('/auth/v1/user', fresh).json()['id'] == users['owner']
        assert api.rows('members', fresh) == owner_members
        print('PASS: expired token denial and refresh recovery; owner must retain rotated refresh token securely')
    else:
        print('Session expiry/refresh not run: supply expired owner JWT and refresh token after approval')
    print('Fixture cleanup requires administrator review. Job/run identifier: ' + job)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', action='store_true')
    parser.add_argument('--write-fixtures', action='store_true')
    parser.add_argument('--storage-fixtures', action='store_true')
    args = parser.parse_args()
    if not args.run:
        print('PLAN ONLY. Target: ' + URL)
        print('Checks: real identities, memberships, anon/unrelated denial; approved synthetic decisions/upserts/health, optional Storage and refresh.')
        print('No users, credentials, real vacancies or cover letters are created. Negative membership writes are expected to be denied.')
        return
    try:
        run(args, os.environ)
    except Exception as exc:
        # Do not expose response bodies, keys, bearer tokens or exception URLs.
        print('FAIL: ' + type(exc).__name__ + '. Inspect the relevant assertion locally; no upstream bodies logged.')
        raise SystemExit(1) from None


if __name__ == '__main__':
    main()
