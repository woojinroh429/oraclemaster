"""The remaining Z3 is not a scheduling gap -- it is an ALLOCATION gap.  The preferred bay
is saturated (blocks fit in it when empty, 0 feasible cells at their own entry time, and
they carry 0-7 units of slack), so no single-block move can help.  What decides Z3 is
WHICH blocks occupy the scarce bay.  Bound: keep the current per-bay occupancy COUNT and
the current schedule, but hand each bay's seats to the blocks with the highest stake in
it.  Ignores packing, so it is an upper bound on any reallocation operator."""
import sys, os, json
HERE = os.path.dirname(os.path.abspath(__file__))
REC = os.path.dirname(HERE)
sys.path.insert(0, REC); os.chdir(REC)
import myalgorithm as M, utils
M._CPP_ENGINE_MODE = M.HAVE_OGC_FAST

def load(p):
    for c in ('data/train/prob_%d.json' % p, 'data/set1/prob_%d.json' % p):
        if os.path.exists(c):
            return json.load(open(c))
    raise SystemExit("prob_%d missing" % p)

for p in (int(x) for x in sys.argv[1].split(',')):
    d = load(p); B = d['blocks']; n = len(B); m = len(d['bays']); w = d['weights']
    sol = M.algorithm(d, timelimit=float(sys.argv[2]))
    c = utils.check_feasibility(d, sol); obj = float(c['objective'])
    bay = {}
    for t, ops in sol['operations'].items():
        for op in ops:
            if op['type'] == 'ENTRY':
                bay[op['block_id']] = op['bay_id']
    cap = [0] * m
    for b in range(n):
        cap[bay[b]] += 1
    cur_z3 = sum(max(B[b]['bay_preferences']) - B[b]['bay_preferences'][bay[b]] for b in range(n))
    # greedy reallocation by regret: repeatedly seat the block that would lose the most
    # by NOT getting its best still-open bay
    left = list(range(n)); rem = cap[:]; got = {}
    while left:
        best = None
        for b in left:
            pv = B[b]['bay_preferences']
            opts = sorted(((pv[j], j) for j in range(m) if rem[j] > 0), reverse=True)
            if not opts:
                break
            regret = opts[0][0] - (opts[1][0] if len(opts) > 1 else opts[0][0])
            key = (regret, opts[0][0])
            if best is None or key > best[0]:
                best = (key, b, opts[0][1])
        if best is None:
            break
        _, b, j = best
        got[b] = j; rem[j] -= 1; left.remove(b)
    new_z3 = sum(max(B[b]['bay_preferences']) - B[b]['bay_preferences'][got[b]] for b in range(n))
    print('p%-3d n=%-4d obj=%-11d cap=%s | Z3 now %6.0f -> realloc %6.0f  (-%.0f pts = %.2f%% of obj)'
          % (p, n, int(obj), cap, cur_z3, new_z3, cur_z3 - new_z3,
             100.0 * w['w3'] * (cur_z3 - new_z3) / obj), flush=True)
