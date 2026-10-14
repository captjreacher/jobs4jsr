from datetime import timedelta

def due_slot(now):
    # One catch-up for the latest due slot, never a burst of historical searches.
    for back in range(8):
        d=now.date()-timedelta(days=back)
        if d.weekday() < 5 and (back or now.hour>=2): return d.isoformat()+'-scheduled'
    raise RuntimeError('No due slot')
