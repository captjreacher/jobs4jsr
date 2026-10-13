from datetime import timedelta

def due_slot(now):
    # One catch-up for the latest due slot, never a burst of historical searches.
    for back in range(8):
        d=now.date()-timedelta(days=back)
        if d.weekday() in (0,2,4) and (back or now.hour>=9): return d.isoformat()+'-scheduled'
    raise RuntimeError('No due slot')
