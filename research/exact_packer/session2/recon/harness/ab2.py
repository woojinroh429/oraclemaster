"""Paired A/B: myalg_v2 against the shipped myalgorithm, same process, same budget.
Lives in the TRACKED harness dir on purpose -- the previous copy was under _n/, which
.gitignore's `_*.py` swallows, so every container reset destroyed it.

    python3.12 harness/ab2.py <probs> <budget_s>
"""
import sys, os, json, time, importlib
HERE = os.path.dirname(os.path.abspath(__file__))
REC = os.path.dirname(HERE)
sys.path.insert(0, REC); os.chdir(REC)
import utils


def load(p):
    for c in ('data/train/prob_%d.json' % p, 'data/set1/prob_%d.json' % p):
        if os.path.exists(c):
            return json.load(open(c))


OLD = importlib.import_module('myalgorithm'); OLD._CPP_ENGINE_MODE = OLD.HAVE_OGC_FAST
NEW = importlib.import_module('myalg_v2');    NEW._CPP_ENGINE_MODE = NEW.HAVE_OGC_FAST
probs = [int(x) for x in sys.argv[1].split(',')]
T = float(sys.argv[2])
w = l = t = 0
for p in probs:
    d = load(p)
    if d is None:
        continue
    row = {}
    for tag, M in (('OLD', OLD), ('V2', NEW)):
        s = M.algorithm(d, timelimit=T)
        c = utils.check_feasibility(d, s)
        row[tag] = (int(c['objective']) if c.get('feasible') else -1,
                    c.get('obj1'), c.get('obj2'), c.get('obj3'))
    a, b = row['OLD'], row['V2']
    g = (100.0 * (b[0] - a[0]) / a[0]) if (a[0] > 0 and b[0] > 0) else float('nan')
    if g < -0.05: w += 1
    elif g > 0.05: l += 1
    else: t += 1
    print('p%-3d n=%-4d OLD=%-11d Z1=%-7s Z2=%-6s Z3=%-8s | V2=%-11d Z1=%-7s Z2=%-6s Z3=%-8s | %+.2f%%'
          % (p, len(d['blocks']), a[0], a[1], a[2], a[3], b[0], b[1], b[2], b[3], g), flush=True)
print('TOTAL v2 wins %d losses %d ties %d' % (w, l, t), flush=True)
