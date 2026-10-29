"""Weekday evening digest over the owner's own SMTP account.

Only roles recorded by a discovery run are emailed. Verified vacancies and
unverified board leads are kept visibly separate so a lead is never mistaken for
a checked advertisement. Each role is labelled with the day it was recorded, so
a role carried over by a missed-day catch-up is never presented as newly found.

Credentials come from the ignored private environment file and are never
logged, printed or written into a report. Only STARTTLS and SSL are accepted:
an unsupported or missing setting is refused rather than downgraded, and the TLS
context verifies the server certificate and hostname before the password is
sent. SMTP has no way to make a message exactly-once; the delivery guarantees
are documented in README.md.
"""
import html
import os
import smtplib
import ssl
from email.message import EmailMessage
from email.utils import formatdate

SECURITY_MODES = ('starttls', 'ssl')
REQUIRED = ('JOBS4JSR_SMTP_HOST', 'JOBS4JSR_SMTP_SECURITY', 'JOBS4JSR_SMTP_USER',
            'JOBS4JSR_SMTP_PASSWORD', 'JOBS4JSR_DIGEST_TO')

# Offered for manual checking only. Indeed returns HTTP 403 to a plain client,
# so it is never fetched automatically.
SAVED_SEARCHES = {
    'SEEK NZ': 'https://nz.seek.com/hospitality-tourism-jobs/in-All-Auckland',
    'Indeed NZ': 'https://nz.indeed.com/jobs?q=hospitality+waiter&l=Auckland',
    'Trade Me': 'https://www.trademe.co.nz/a/jobs/hospitality-tourism/auckland/auckland-city',
}


def security():
    """The configured transport, or a refusal. An unknown setting never downgrades."""
    value = (os.environ.get('JOBS4JSR_SMTP_SECURITY') or '').strip().lower()
    if value not in SECURITY_MODES:
        raise ValueError(
            'Unsupported SMTP security setting ' + repr(value) + ': set JOBS4JSR_SMTP_SECURITY to '
            '"starttls" or "ssl". Credentials are never sent over an unencrypted connection.')
    return value


def check_configuration():
    """Raise a clear, credential-free error naming what is missing."""
    missing = [name for name in REQUIRED if not os.environ.get(name)]
    if missing:
        raise ValueError('Digest email is not configured: set ' + ', '.join(missing) +
                         ' in the private environment file. No credentials are inferred.')
    return security()


def configured():
    try:
        check_configuration()
    except ValueError:
        return False
    return True


def _label(day):
    return f'{day:%A} {day.day} {day:%B %Y}'


def _short(day):
    return f'{day.day} {day:%B}'


def _text(role):
    return ' — '.join(str(part) for part in role if part)


def _vacancy_details(job):
    return [job['location'], f"{job['distance']:.1f} km approx", job.get('job_type'),
            job.get('pay') or job.get('salary'), job.get('hours')]


def _lead_details(lead):
    return [lead.get('employer'), lead.get('location'), lead.get('pay'),
            lead.get('listed') or lead.get('posted')]


def build(today, groups):
    """Return (subject, text, html) for the days supplied, newest last.

    ``groups`` is a list of ``{'day': date, 'jobs': [...], 'leads': [...]}``.
    Every role is attributed to the day it was recorded, so a catch-up digest is
    never mistaken for a fresh discovery.
    """
    total = sum(len(group['jobs']) + len(group['leads']) for group in groups)
    subject = f'Jobs4JSR: {total} new role{"" if total == 1 else "s"} — {_label(today)}'
    earlier = [group['day'] for group in groups if group['day'] != today]
    if earlier:
        subject += ' (catching up on ' + ', '.join(_short(day) for day in earlier) + ')'
    catch_up = bool(earlier)

    text = [f'Jobs4JSR new roles for {_label(today)}.', '']
    if catch_up:
        text += ['A scheduled digest was missed, so this email also covers earlier weekdays. '
                 'Each role is labelled with the day it was recorded.', '']
    rows = []
    heading = f'<h1>Jobs4JSR new roles — {html.escape(_label(today))}</h1>'
    if catch_up:
        heading += ('<p>An earlier digest was missed, so this email also covers those weekdays. '
                    'Each role is labelled with the day it was recorded.</p>')
    for group in groups:
        jobs, leads = group['jobs'], group['leads']
        if catch_up or group['day'] != today:
            when = _label(group['day'])
            text += [f'Recorded on {when} — found by that day\'s search, not today:', '']
            rows.append(f'<h2>Recorded on {html.escape(when)}</h2>'
                        '<p>Found by that day\'s search, not today.</p>')
        if jobs:
            text += [f'{len(jobs)} newly retained vacancy(ies) — advert verified, letter available in the local report:', '']
            text += ['- ' + _text([f"{job['employer']} — {job['title']}"] + _vacancy_details(job) + [job['url']])
                     for job in jobs] + ['']
            rows.append(f'<h2>{len(jobs)} new vacancies</h2><ul>')
            for job in jobs:
                rows.append('<li><strong>' + html.escape(f"{job['employer']} — {job['title']}") + '</strong><br>'
                            + html.escape(_text(_vacancy_details(job))) + '<br>'
                            + f'<a href="{html.escape(job["url"], quote=True)}">View advertisement</a></li>')
            rows.append('</ul>')
        if leads:
            text += [f'{len(leads)} unverified lead(s) — open these yourself; no advert was fetched:', '']
            text += ['- ' + _text([f"{lead['board']}: {lead['title']}"] + _lead_details(lead) + [lead['url']])
                     for lead in leads] + ['']
            rows.append(f'<h2>{len(leads)} unverified leads</h2><p>No advert was fetched. Open and check each one.</p><ul>')
            for lead in leads:
                rows.append('<li><strong>' + html.escape(f"{lead['board']}: {lead['title']}") + '</strong><br>'
                            + html.escape(_text(_lead_details(lead))) + '<br>'
                            + f'<a href="{html.escape(lead["url"], quote=True)}">Open listing</a></li>')
            rows.append('</ul>')

    text += ['Boards to check manually (not scraped):', '']
    text += [f'- {name}: {url}' for name, url in SAVED_SEARCHES.items()]
    text += ['', 'Leads carry no verified workplace coordinate and no confirmed application action, '
             'so they have no distance, score or letter. Review every advert before applying.']

    rows.append('<h2>Boards to check manually</h2><ul>')
    rows += [f'<li><a href="{html.escape(url, quote=True)}">{html.escape(name)}</a></li>'
             for name, url in SAVED_SEARCHES.items()]
    rows.append('</ul>')
    body = ('<!doctype html><html lang="en-NZ"><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width, initial-scale=1">'
            f'<title>{html.escape(subject)}</title>'
            '<body style="font:16px system-ui;color:#17313b;background:#f4f7f9;margin:24px">'
            + heading + ''.join(rows)
            + '<p>Leads have no verified workplace coordinate and no confirmed application action, '
              'so they carry no distance, score or letter. Review every advert before applying.</p></body></html>')
    return subject, '\n'.join(text), body


def send(subject, text, html_body):
    mode = check_configuration()
    host = os.environ['JOBS4JSR_SMTP_HOST']
    try:
        port = int(os.environ.get('JOBS4JSR_SMTP_PORT') or (465 if mode == 'ssl' else 587))
    except ValueError:
        raise ValueError('Invalid JOBS4JSR_SMTP_PORT: it must be a number.')
    sender = os.environ.get('JOBS4JSR_DIGEST_FROM') or os.environ['JOBS4JSR_SMTP_USER']
    message = EmailMessage()
    message['Subject'] = subject
    message['From'] = sender
    message['To'] = os.environ['JOBS4JSR_DIGEST_TO']
    message['Date'] = formatdate(localtime=True)
    message.set_content(text)
    message.add_alternative(html_body, subtype='html')
    # create_default_context verifies the chain and the hostname. smtplib's own
    # default context disables verification, which would encrypt the password to
    # any server able to intercept the connection.
    context = ssl.create_default_context()
    if mode == 'ssl':
        with smtplib.SMTP_SSL(host, port, timeout=30, context=context) as server:
            server.login(os.environ['JOBS4JSR_SMTP_USER'], os.environ['JOBS4JSR_SMTP_PASSWORD'])
            server.send_message(message)
    else:
        with smtplib.SMTP(host, port, timeout=30) as server:
            server.starttls(context=context)
            server.login(os.environ['JOBS4JSR_SMTP_USER'], os.environ['JOBS4JSR_SMTP_PASSWORD'])
            server.send_message(message)
    return subject
