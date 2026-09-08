import sys

sys.path.insert(0,'D:/hydrolib')
try:
    from core.stats.kritsky_tables import get_ordinates
    r = get_ordinates(1.2, 0.35)
    print('Kritsky PASS:', type(r), 'len=', len(r))
except Exception as e:
    print('Kritsky ERROR:', type(e).__name__, str(e)[:300])
